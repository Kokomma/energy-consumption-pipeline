"""
transform.py
============
Cleans, validates, and enriches raw Nigerian energy datasets.
Handles missing values, unit conversions, and derived metrics.

Author: Ella | NSERC Portfolio Project DE-001
"""

import pandas as pd
import numpy as np
import os
from loguru import logger
from datetime import datetime

logger.add("logs/etl_{time}.log", rotation="10 MB", level="INFO")


# ─────────────────────────────────────────────
# Validation Rules
# ─────────────────────────────────────────────
CONSUMPTION_RULES = {
    "energy_injected_mwh": (0, 200_000),
    "energy_billed_mwh":   (0, 150_000),
    "loss_rate_pct":       (0, 80),
    "tariff_rate_ngn_kwh": (1, 200),
    "hours_of_supply":     (0, 24),
    "collection_efficiency_pct": (0, 100),
}


def validate_dataframe(df: pd.DataFrame, rules: dict, name: str) -> pd.DataFrame:
    """Clip values to valid ranges and log anomalies."""
    total_anomalies = 0
    for col, (min_val, max_val) in rules.items():
        if col not in df.columns:
            continue
        mask = (df[col] < min_val) | (df[col] > max_val)
        count = mask.sum()
        if count > 0:
            logger.warning(f"{name}: {count} anomalies in '{col}' — clipping to [{min_val}, {max_val}]")
            df[col] = df[col].clip(min_val, max_val)
            total_anomalies += count
    logger.info(f"{name}: {total_anomalies} total anomalies corrected")
    return df


def transform_consumption(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("Transforming consumption data...")

    # Parse dates
    df["record_date"] = pd.to_datetime(df["record_date"])
    df["quarter"] = df["record_date"].dt.quarter
    df["quarter_label"] = "Q" + df["quarter"].astype(str) + " " + df["year"].astype(str)

    # Handle nulls
    numeric_cols = df.select_dtypes(include=np.number).columns
    df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].median())

    # Validate
    df = validate_dataframe(df, CONSUMPTION_RULES, "consumption")

    # Derived metrics
    df["atc_c_loss_pct"] = df["loss_rate_pct"]  # Aggregate Technical, Commercial & Collection
    df["revenue_collected_ngn_m"] = (
        df["revenue_ngn_millions"] * df["collection_efficiency_pct"] / 100
    ).round(2)
    df["energy_per_customer_kwh"] = (
        (df["energy_billed_mwh"] * 1000) / df["customer_count"].replace(0, np.nan)
    ).round(2)
    df["tariff_band"] = pd.cut(
        df["hours_of_supply"],
        bins=[0, 4, 8, 12, 16, 24],
        labels=["Band E", "Band D", "Band C", "Band B", "Band A"],
        right=True
    )
    df["region"] = df["disco"].map({
        "Abuja DisCo": "North Central",   "Jos DisCo": "North Central",
        "Kaduna DisCo": "North West",     "Kano DisCo": "North West",
        "Yola DisCo": "North East",       "Eko DisCo": "South West",
        "Ikeja DisCo": "South West",      "Ibadan DisCo": "South West",
        "Enugu DisCo": "South East",      "Port Harcourt DisCo": "South South",
        "Benin DisCo": "South South",
    })

    logger.success(f"Consumption transform complete: {len(df):,} rows")
    return df


def transform_outages(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("Transforming outage data...")

    df["start_datetime"] = pd.to_datetime(df["start_datetime"])
    df["end_datetime"]   = pd.to_datetime(df["end_datetime"])
    df["year"]  = df["start_datetime"].dt.year
    df["month"] = df["start_datetime"].dt.month
    df["hour_of_day"] = df["start_datetime"].dt.hour
    df["day_of_week"]  = df["start_datetime"].dt.day_name()

    # Recalculate duration in case of data inconsistency
    df["duration_hours_calc"] = (
        (df["end_datetime"] - df["start_datetime"]).dt.total_seconds() / 3600
    ).round(2)

    df["saidi_minutes"] = (df["duration_hours"] * 60 * df["customers_affected"]).round(0)
    df["saifi_events"]  = 1  # each row = 1 interruption event

    df["cause_grouped"] = df["cause_category"].map({
        "Conductor Failure": "Technical",   "Transformer Fault": "Technical",
        "Cable Fault": "Technical",         "Equipment Overload": "Technical",
        "Substation Tripping": "Technical", "Metering Fault": "Technical",
        "Tree Contact": "Environmental",    "Storm Damage": "Environmental",
        "Vandalism": "Non-Technical",       "Billing Disconnect": "Non-Technical",
        "Load Shedding (GENCO)": "System",
    }).fillna("Other")

    logger.success(f"Outage transform complete: {len(df):,} rows")
    return df


def transform_renewable(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("Transforming renewable data...")

    df["record_date"] = pd.to_datetime(df["record_date"])
    df["quarter"] = df["record_date"].dt.quarter

    # Renewable share (compared to avg grid injection)
    avg_grid_mwh_monthly = 3_200_000  # Nigeria avg ~3.2 TWh/month total
    df["grid_share_pct"] = (df["generation_mwh"] / avg_grid_mwh_monthly * 100).round(4)

    df["lcoe_estimate_usd_mwh"] = df["renewable_type"].map({
        "Solar_PV": 45,
        "Small_Hydro": 55,
        "Wind": 65,
        "Biomass": 80,
    })

    logger.success(f"Renewable transform complete: {len(df):,} rows")
    return df


def run_pipeline():
    os.makedirs("data/processed", exist_ok=True)
    os.makedirs("logs", exist_ok=True)

    logger.info("=" * 60)
    logger.info("NSERC Energy ETL Pipeline — Transform Stage")
    logger.info(f"Run timestamp: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    # Load raw data
    df_c = pd.read_csv("data/raw/consumption.csv")
    df_o = pd.read_csv("data/raw/outages.csv")
    df_r = pd.read_csv("data/raw/renewable.csv")

    logger.info(f"Loaded: {len(df_c):,} consumption | {len(df_o):,} outages | {len(df_r):,} renewable")

    # Transform
    df_c = transform_consumption(df_c)
    df_o = transform_outages(df_o)
    df_r = transform_renewable(df_r)

    # Save
    df_c.to_csv("data/processed/consumption_clean.csv", index=False)
    df_o.to_csv("data/processed/outages_clean.csv", index=False)
    df_r.to_csv("data/processed/renewable_clean.csv", index=False)

    logger.success("All processed files saved to data/processed/")
    logger.info("Next step: Run sql/load_warehouse.py to populate the data warehouse.")


if __name__ == "__main__":
    run_pipeline()
