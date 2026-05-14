"""
load_warehouse.py
=================
Loads transformed CSVs into the PostgreSQL data warehouse.
Populates dimension tables first, then fact tables.

Author: Ella | NSERC Portfolio Project DE-001
"""

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from loguru import logger
import os

load_dotenv()

DB_URL = (
    f"postgresql://{os.getenv('DB_USER', 'postgres')}:"
    f"{os.getenv('DB_PASSWORD', 'postgres')}@"
    f"{os.getenv('DB_HOST', 'localhost')}:"
    f"{os.getenv('DB_PORT', '5432')}/"
    f"{os.getenv('DB_NAME', 'nigeria_energy_db')}"
)

DISCOS_META = {
    "Abuja DisCo":         {"region": "North Central", "hq": "Abuja",        "states": "FCT, Niger, Nasarawa, Kogi",               "privatised": 2013},
    "Benin DisCo":         {"region": "South South",   "hq": "Benin City",   "states": "Edo, Delta, Ondo",                         "privatised": 2013},
    "Eko DisCo":           {"region": "South West",    "hq": "Lagos",        "states": "Lagos (South)",                            "privatised": 2013},
    "Enugu DisCo":         {"region": "South East",    "hq": "Enugu",        "states": "Enugu, Ebonyi, Anambra, Abia",             "privatised": 2013},
    "Ibadan DisCo":        {"region": "South West",    "hq": "Ibadan",       "states": "Oyo, Ogun, Osun, Kwara",                   "privatised": 2013},
    "Ikeja DisCo":         {"region": "South West",    "hq": "Ikeja",        "states": "Lagos (North)",                            "privatised": 2013},
    "Jos DisCo":           {"region": "North Central", "hq": "Jos",          "states": "Plateau, Benue, Nassarawa",                "privatised": 2013},
    "Kaduna DisCo":        {"region": "North West",    "hq": "Kaduna",       "states": "Kaduna, Kebbi, Sokoto, Zamfara",           "privatised": 2013},
    "Kano DisCo":          {"region": "North West",    "hq": "Kano",         "states": "Kano, Jigawa, Katsina",                    "privatised": 2013},
    "Port Harcourt DisCo": {"region": "South South",   "hq": "Port Harcourt","states": "Rivers, Bayelsa, Akwa Ibom, Cross River",  "privatised": 2013},
    "Yola DisCo":          {"region": "North East",    "hq": "Yola",         "states": "Adamawa, Taraba, Borno, Yobe, Gombe",      "privatised": 2013},
}


def get_engine():
    engine = create_engine(DB_URL, echo=False)
    logger.info(f"Connected to database: {os.getenv('DB_NAME', 'nigeria_energy_db')}")
    return engine


def load_schema(engine):
    with open("sql/schema.sql", "r") as f:
        schema_sql = f.read()
    with engine.connect() as conn:
        conn.execute(text(schema_sql))
        conn.commit()
    logger.success("Schema created / verified")


def populate_dim_disco(engine):
    rows = []
    for disco_name, meta in DISCOS_META.items():
        rows.append({
            "disco_name":     disco_name,
            "region":         meta["region"],
            "headquarters":   meta["hq"],
            "states_covered": meta["states"],
            "privatised_year":meta["privatised"],
            "is_active":      True,
        })
    df = pd.DataFrame(rows)
    with engine.connect() as conn:
        for _, row in df.iterrows():
            conn.execute(text("""
                INSERT INTO dim_disco (disco_name, region, headquarters, states_covered, privatised_year, is_active)
                VALUES (:disco_name, :region, :headquarters, :states_covered, :privatised_year, :is_active)
                ON CONFLICT (disco_name) DO NOTHING
            """), row.to_dict())
        conn.commit()
    logger.success(f"dim_disco: {len(rows)} DisCos loaded")


def populate_dim_date(engine):
    dates = pd.date_range("2019-01-01", "2024-12-31", freq="D")
    rows = []
    for d in dates:
        rows.append({
            "full_date":    d.date(),
            "year":         d.year,
            "quarter":      d.quarter,
            "quarter_label":f"Q{d.quarter} {d.year}",
            "month":        d.month,
            "month_name":   d.strftime("%B"),
            "day_of_month": d.day,
            "day_of_week":  d.strftime("%A"),
            "is_weekend":   d.weekday() >= 5,
            "fiscal_year":  d.year,
        })
    df = pd.DataFrame(rows)
    df.to_sql("dim_date", engine, if_exists="append", index=False,
              method="multi", chunksize=500)
    logger.success(f"dim_date: {len(rows):,} dates loaded")


def load_fact_consumption(engine, df_c: pd.DataFrame):
    with engine.connect() as conn:
        # Get lookup maps
        date_map  = pd.read_sql("SELECT date_key, full_date FROM dim_date", conn)
        disco_map = pd.read_sql("SELECT disco_key, disco_name FROM dim_disco", conn)
        class_map = pd.read_sql("SELECT class_key, class_name FROM dim_customer_class", conn)
        band_map  = pd.read_sql("SELECT band_key, band_name FROM dim_tariff_band", conn)

    date_map["full_date"] = pd.to_datetime(date_map["full_date"]).dt.date
    df_c["record_date_d"] = pd.to_datetime(df_c["record_date"]).dt.date

    df_c = df_c.merge(date_map.rename(columns={"full_date": "record_date_d"}), on="record_date_d", how="left")
    df_c = df_c.merge(disco_map, left_on="disco",          right_on="disco_name", how="left")
    df_c = df_c.merge(class_map, left_on="customer_class", right_on="class_name", how="left")
    df_c = df_c.merge(band_map,  left_on="tariff_band",    right_on="band_name",  how="left")

    fact_cols = [
        "date_key", "disco_key", "class_key", "band_key",
        "energy_injected_mwh", "energy_billed_mwh", "system_loss_mwh",
        "loss_rate_pct", "atc_c_loss_pct", "hours_of_supply",
        "collection_efficiency_pct", "tariff_rate_ngn_kwh",
        "revenue_ngn_millions", "revenue_collected_ngn_m",
        "customer_count", "energy_per_customer_kwh",
        "state", "region",
    ]
    df_fact = df_c[[c for c in fact_cols if c in df_c.columns]].dropna(subset=["date_key", "disco_key"])
    df_fact.to_sql("fact_consumption", engine, if_exists="append", index=False,
                   method="multi", chunksize=500)
    logger.success(f"fact_consumption: {len(df_fact):,} rows loaded")


def load_fact_outages(engine, df_o: pd.DataFrame):
    with engine.connect() as conn:
        date_map  = pd.read_sql("SELECT date_key, full_date FROM dim_date", conn)
        disco_map = pd.read_sql("SELECT disco_key, disco_name FROM dim_disco", conn)

    date_map["full_date"] = pd.to_datetime(date_map["full_date"]).dt.date
    df_o["start_date"] = pd.to_datetime(df_o["start_datetime"]).dt.date

    df_o = df_o.merge(date_map.rename(columns={"full_date": "start_date"}), on="start_date", how="left")
    df_o = df_o.merge(disco_map, left_on="disco", right_on="disco_name", how="left")

    fact_cols = [
        "outage_id", "date_key", "disco_key",
        "start_datetime", "end_datetime", "duration_hours",
        "response_time_hrs", "customers_affected", "mwh_lost",
        "saidi_minutes", "saifi_events",
        "cause_category", "cause_grouped", "severity",
        "affected_state", "fault_location", "resolved",
    ]
    df_fact = df_o[[c for c in fact_cols if c in df_o.columns]].dropna(subset=["date_key", "disco_key"])
    df_fact.to_sql("fact_outages", engine, if_exists="append", index=False,
                   method="multi", chunksize=500)
    logger.success(f"fact_outages: {len(df_fact):,} rows loaded")


def load_fact_renewable(engine, df_r: pd.DataFrame):
    with engine.connect() as conn:
        date_map = pd.read_sql("SELECT date_key, full_date FROM dim_date", conn)
        type_map = pd.read_sql("SELECT type_key, type_name FROM dim_renewable_type", conn)

    date_map["full_date"] = pd.to_datetime(date_map["full_date"]).dt.date
    df_r["record_date_d"] = pd.to_datetime(df_r["record_date"]).dt.date

    df_r = df_r.merge(date_map.rename(columns={"full_date": "record_date_d"}), on="record_date_d", how="left")
    df_r = df_r.merge(type_map, left_on="renewable_type", right_on="type_name", how="left")

    fact_cols = [
        "date_key", "type_key", "state",
        "installed_capacity_mw", "generation_mwh", "capacity_factor_pct",
        "grid_share_pct", "co2_avoided_tonnes", "project_count",
        "investment_usd_millions", "lcoe_estimate_usd_mwh",
    ]
    df_fact = df_r[[c for c in fact_cols if c in df_r.columns]].dropna(subset=["date_key", "type_key"])
    df_fact.to_sql("fact_renewable", engine, if_exists="append", index=False,
                   method="multi", chunksize=500)
    logger.success(f"fact_renewable: {len(df_fact):,} rows loaded")


def run_load():
    logger.info("=" * 60)
    logger.info("NSERC Energy ETL Pipeline — Load Stage")
    logger.info("=" * 60)

    engine = get_engine()
    load_schema(engine)
    populate_dim_disco(engine)
    populate_dim_date(engine)

    df_c = pd.read_csv("data/processed/consumption_clean.csv")
    df_o = pd.read_csv("data/processed/outages_clean.csv")
    df_r = pd.read_csv("data/processed/renewable_clean.csv")

    load_fact_consumption(engine, df_c)
    load_fact_outages(engine, df_o)
    load_fact_renewable(engine, df_r)

    logger.success("✅ All data loaded to warehouse. Open Power BI → connect to PostgreSQL.")


if __name__ == "__main__":
    run_load()
