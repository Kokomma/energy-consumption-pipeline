"""
generate_data.py
================
Generates realistic Nigerian power sector datasets for the ETL pipeline.
Simulates data from 11 DisCos, 36 states + FCT, across 5 years.

Author: Ella | NSERC Portfolio Project DE-001
"""

import pandas as pd
import numpy as np
from faker import Faker
from datetime import datetime, timedelta
import random
import os

fake = Faker()
random.seed(42)
np.random.seed(42)

# ─────────────────────────────────────────────
# Nigerian Power Sector Constants
# ─────────────────────────────────────────────
DISCOS = [
    "Abuja DisCo", "Benin DisCo", "Eko DisCo", "Enugu DisCo",
    "Ibadan DisCo", "Ikeja DisCo", "Jos DisCo", "Kaduna DisCo",
    "Kano DisCo", "Port Harcourt DisCo", "Yola DisCo"
]

STATES = {
    "Abuja DisCo":        ["FCT", "Niger", "Nasarawa", "Kogi"],
    "Benin DisCo":        ["Edo", "Delta", "Ondo"],
    "Eko DisCo":          ["Lagos (South)"],
    "Enugu DisCo":        ["Enugu", "Ebonyi", "Anambra", "Abia"],
    "Ibadan DisCo":       ["Oyo", "Ogun", "Osun", "Kwara"],
    "Ikeja DisCo":        ["Lagos (North)"],
    "Jos DisCo":          ["Plateau", "Benue", "Nassarawa"],
    "Kaduna DisCo":       ["Kaduna", "Kebbi", "Sokoto", "Zamfara"],
    "Kano DisCo":         ["Kano", "Jigawa", "Katsina"],
    "Port Harcourt DisCo":["Rivers", "Bayelsa", "Akwa Ibom", "Cross River"],
    "Yola DisCo":         ["Adamawa", "Taraba", "Borno", "Yobe", "Gombe"],
}

CUSTOMER_CLASSES = ["Residential_LV", "Commercial_LV", "Industrial_HV", "Special_Load_HV"]
VOLTAGE_LEVELS = {"Residential_LV": "LV", "Commercial_LV": "LV",
                  "Industrial_HV": "HV", "Special_Load_HV": "HV"}
RENEWABLE_TYPES = ["Solar_PV", "Small_Hydro", "Wind", "Biomass"]

# Base tariff rates (₦/kWh) approximate 2023 NERC rates
TARIFF_RATES = {
    "Residential_LV":  {"R1": 4.00, "R2": 45.00, "R3": 62.15},
    "Commercial_LV":   {"C1": 56.00, "C2": 63.50, "C3": 69.80},
    "Industrial_HV":   {"D1": 55.72, "D2": 59.10, "D3": 63.00},
    "Special_Load_HV": {"S1": 55.72, "S2": 59.10},
}


def generate_monthly_consumption(start_year=2019, end_year=2024):
    """
    Generate monthly energy consumption records per DisCo per customer class.
    Returns a DataFrame with 3,960+ rows.
    """
    records = []
    date = datetime(start_year, 1, 1)
    end_date = datetime(end_year, 12, 31)

    while date <= end_date:
        for disco in DISCOS:
            states = STATES[disco]
            for cust_class in CUSTOMER_CLASSES:
                # Seasonal variation (higher in dry season - Oct-Mar)
                month = date.month
                seasonal_factor = 1.15 if month in [11, 12, 1, 2, 3] else (
                    0.85 if month in [6, 7, 8] else 1.0
                )

                # DisCo-specific capacity factor (Ikeja/Eko higher, Yola/Jos lower)
                disco_factor = {
                    "Ikeja DisCo": 1.4, "Eko DisCo": 1.35, "Abuja DisCo": 1.2,
                    "Kano DisCo": 1.1, "Port Harcourt DisCo": 1.05,
                    "Ibadan DisCo": 1.0, "Kaduna DisCo": 0.95, "Enugu DisCo": 0.9,
                    "Benin DisCo": 0.88, "Jos DisCo": 0.75, "Yola DisCo": 0.6,
                }.get(disco, 1.0)

                # Base consumption by customer class (MWh/month)
                base_consumption = {
                    "Residential_LV":   random.uniform(8_000, 25_000),
                    "Commercial_LV":    random.uniform(5_000, 18_000),
                    "Industrial_HV":    random.uniform(15_000, 60_000),
                    "Special_Load_HV":  random.uniform(10_000, 35_000),
                }.get(cust_class, 10_000)

                # Year-on-year growth trend (+3% annually)
                year_factor = 1 + 0.03 * (date.year - start_year)

                energy_mwh = base_consumption * seasonal_factor * disco_factor * year_factor
                energy_mwh *= random.uniform(0.88, 1.12)  # noise

                # System losses (NTL + technical) — Nigeria averages 40-55%
                loss_rate = random.uniform(0.35, 0.55)
                billed_mwh = energy_mwh * (1 - loss_rate)

                # Revenue calculation
                voltage = VOLTAGE_LEVELS[cust_class]
                tariff_rate = random.uniform(45.0, 69.8)  # ₦/kWh blended

                records.append({
                    "record_date":      date.strftime("%Y-%m-%d"),
                    "year":             date.year,
                    "month":            date.month,
                    "month_name":       date.strftime("%B"),
                    "disco":            disco,
                    "state":            random.choice(states),
                    "customer_class":   cust_class,
                    "voltage_level":    voltage,
                    "energy_injected_mwh":  round(energy_mwh, 2),
                    "energy_billed_mwh":    round(billed_mwh, 2),
                    "system_loss_mwh":      round(energy_mwh - billed_mwh, 2),
                    "loss_rate_pct":        round(loss_rate * 100, 2),
                    "tariff_rate_ngn_kwh":  round(tariff_rate, 2),
                    "revenue_ngn_millions": round((billed_mwh * 1000 * tariff_rate) / 1_000_000, 2),
                    "customer_count":       int(random.uniform(5_000, 80_000) * disco_factor),
                    "collection_efficiency_pct": round(random.uniform(55, 92), 2),
                    "hours_of_supply":      round(random.uniform(6, 20), 1),
                })

        date += timedelta(days=32)
        date = date.replace(day=1)

    return pd.DataFrame(records)


def generate_outage_log(n=5000):
    """
    Generate outage incident records with root cause, duration, and affected customers.
    """
    records = []
    outage_causes = [
        "Conductor Failure", "Transformer Fault", "Vandalism", "Tree Contact",
        "Load Shedding (GENCO)", "Billing Disconnect", "Storm Damage",
        "Equipment Overload", "Cable Fault", "Substation Tripping", "Metering Fault"
    ]
    affected_zones = [s for states in STATES.values() for s in states]

    for _ in range(n):
        start_dt = fake.date_time_between(start_date="-5y", end_date="now")
        duration_hrs = round(random.expovariate(1 / 8), 1)  # avg 8hr outage
        duration_hrs = min(duration_hrs, 72)

        disco = random.choice(DISCOS)
        cause = random.choice(outage_causes)

        records.append({
            "outage_id":          fake.uuid4()[:12].upper(),
            "disco":              disco,
            "affected_state":     random.choice(STATES[disco]),
            "start_datetime":     start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "end_datetime":       (start_dt + timedelta(hours=duration_hrs)).strftime("%Y-%m-%d %H:%M:%S"),
            "duration_hours":     duration_hrs,
            "cause_category":     cause,
            "severity":           "Critical" if duration_hrs > 24 else ("High" if duration_hrs > 8 else "Medium"),
            "customers_affected": int(random.uniform(500, 45_000)),
            "mwh_lost":           round(random.uniform(10, 5_000), 1),
            "response_time_hrs":  round(random.uniform(0.5, 12), 1),
            "fault_location":     f"Feeder {random.randint(1,30):02d} / {fake.street_name()}",
            "resolved":           random.choices([True, False], weights=[0.92, 0.08])[0],
        })

    return pd.DataFrame(records)


def generate_renewable_energy(start_year=2019, end_year=2024):
    """
    Generate renewable energy generation data for Nigeria.
    """
    records = []
    date = datetime(start_year, 1, 1)
    end_date = datetime(end_year, 12, 31)

    solar_states = ["Lagos (North)", "FCT", "Kano", "Kaduna", "Plateau"]
    hydro_states  = ["Niger", "Plateau", "Kogi", "Enugu"]
    wind_states   = ["Katsina", "Sokoto", "Zamfara"]

    while date <= end_date:
        month = date.month
        for rtype in RENEWABLE_TYPES:
            if rtype == "Solar_PV":
                # Solar peaks in dry season
                seasonal = 1.3 if month in [11, 12, 1, 2, 3] else 0.8
                state = random.choice(solar_states)
                capacity_mw = random.uniform(5, 120)
            elif rtype == "Small_Hydro":
                # Hydro peaks in rainy season
                seasonal = 1.4 if month in [6, 7, 8, 9] else 0.7
                state = random.choice(hydro_states)
                capacity_mw = random.uniform(10, 80)
            elif rtype == "Wind":
                seasonal = random.uniform(0.7, 1.2)
                state = random.choice(wind_states)
                capacity_mw = random.uniform(2, 40)
            else:  # Biomass
                seasonal = 1.0
                state = random.choice([s for states in STATES.values() for s in states])
                capacity_mw = random.uniform(1, 20)

            capacity_factor = random.uniform(0.15, 0.45) * seasonal
            generation_mwh = capacity_mw * capacity_factor * 730  # hrs/month
            year_growth = 1 + 0.08 * (date.year - start_year)  # 8% YoY growth

            records.append({
                "record_date":      date.strftime("%Y-%m-%d"),
                "year":             date.year,
                "month":            date.month,
                "state":            state,
                "renewable_type":   rtype,
                "installed_capacity_mw": round(capacity_mw * year_growth, 2),
                "generation_mwh":   round(generation_mwh * year_growth, 2),
                "capacity_factor_pct": round(capacity_factor * 100, 2),
                "co2_avoided_tonnes": round(generation_mwh * 0.43, 2),  # Nigeria grid emission factor
                "project_count":    random.randint(1, 15),
                "investment_usd_millions": round(capacity_mw * random.uniform(0.8, 2.5), 2),
            })

        date += timedelta(days=32)
        date = date.replace(day=1)

    return pd.DataFrame(records)


if __name__ == "__main__":
    os.makedirs("data/raw", exist_ok=True)

    print("⚡ Generating Nigerian Energy Consumption data...")
    df_consumption = generate_monthly_consumption()
    df_consumption.to_csv("data/raw/consumption.csv", index=False)
    print(f"   ✓ {len(df_consumption):,} consumption records → data/raw/consumption.csv")

    print("⚠️  Generating Outage Log data...")
    df_outages = generate_outage_log(5000)
    df_outages.to_csv("data/raw/outages.csv", index=False)
    print(f"   ✓ {len(df_outages):,} outage records → data/raw/outages.csv")

    print("🌱 Generating Renewable Energy data...")
    df_renewable = generate_renewable_energy()
    df_renewable.to_csv("data/raw/renewable.csv", index=False)
    print(f"   ✓ {len(df_renewable):,} renewable records → data/raw/renewable.csv")

    print("\n✅ Data generation complete. Run etl/transform.py next.")
