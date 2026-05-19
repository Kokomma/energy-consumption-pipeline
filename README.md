# ⚡ Energy Consumption Pipeline — DE-001

> **A production-grade ETL pipeline for Nigerian power sector data, feeding a star-schema SQL warehouse and Power BI dashboard.**

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?logo=postgresql)
![Azure](https://img.shields.io/badge/Azure-Storage-0078D4?logo=microsoftazure)
![Power BI](https://img.shields.io/badge/Power%20BI-Dashboard-F2C811?logo=powerbi)

---

## 🎯 Problem Statement

Nigeria's power sector — comprising 11 Distribution Companies (DisCos), 6 GenCos, and the NBET market — generates enormous volumes of consumption, outage, and billing data that is currently siloed in spreadsheets across multiple organisations.

**The cost of this fragmentation:**
- Regulators (NERC/NSERC) lack real-time data to enforce service quality benchmarks
- DisCos cannot trend their ATC&C losses without manual monthly aggregation
- No consolidated view of renewable energy integration into the grid exists

**This project solves it** by building an automated ETL pipeline that ingests, cleans, and warehouses 3+ years of energy data, then surfaces insights through a Power BI dashboard.

---

## 🗂️ Project Structure

```
project1-energy-pipeline/
├── etl/
│   ├── generate_data.py      # Generates realistic Nigerian energy datasets
│   └── transform.py          # Cleans, validates, enriches raw data
├── sql/
│   ├── schema.sql            # Star-schema DDL (PostgreSQL/Azure SQL)
│   └── load_warehouse.py     # Populates warehouse from processed CSVs
├── data/
│   ├── raw/                  # Raw CSVs (generated)
│   └── processed/            # Cleaned CSVs (transformed)
├── dashboard/
│   └── POWERBI_SETUP.md      # Step-by-step Power BI connection guide
├── docs/
│   └── architecture.md       # System architecture description
├── .env.example
└── requirements.txt
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    DATA SOURCES                          │
│  NERC Monthly Reports | World Bank | IRENA | Simulated  │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│                  EXTRACT (Python)                        │
│  generate_data.py → data/raw/*.csv                      │
│  • consumption.csv  • outages.csv  • renewable.csv      │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│                TRANSFORM (Pandas)                        │
│  transform.py → data/processed/*_clean.csv              │
│  • Null handling      • Range validation                 │
│  • Derived metrics    • Tariff band classification       │
│  • Regional mapping   • SAIDI/SAIFI calculation          │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│              LOAD (SQLAlchemy → PostgreSQL)              │
│  Star Schema: 5 Dims + 3 Facts + 3 Analytical Views     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │dim_disco     │  │dim_date      │  │dim_tariff_band│  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         └────────────┬────┘                  │          │
│                      ▼                       │          │
│              ┌───────────────┐               │          │
│              │fact_consumption│◄─────────────┘          │
│              │fact_outages   │                          │
│              │fact_renewable │                          │
│              └───────────────┘                          │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│                 VISUALISE (Power BI)                     │
│  • DisCo performance heatmap (11 DisCos × 5 years)      │
│  • ATC&C loss trend by region                           │
│  • SAIDI/SAIFI outage quality index                     │
│  • Renewable energy mix evolution 2019–2024             │
│  • Revenue collection efficiency by tariff band         │
└─────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 15+ (or Azure SQL Database)
- Power BI Desktop (free)

### Step 1 — Clone & Install
```bash
git clone https://github.com/Kokomma/energy-consumption-pipeline
cd energy-consumption-pipeline
pip install -r requirements.txt
```

### Step 2 — Configure Environment
```bash
cp .env.example .env
# Edit .env with your PostgreSQL credentials
```

### Step 3 — Generate Data
```bash
python etl/generate_data.py
# Output: data/raw/consumption.csv (3,960 rows)
#         data/raw/outages.csv     (5,000 rows)
#         data/raw/renewable.csv   (1,440 rows)
```

### Step 4 — Transform
```bash
python etl/transform.py
# Output: data/processed/*_clean.csv
#         logs/etl_TIMESTAMP.log
```

### Step 5 — Load Warehouse
```bash
python sql/load_warehouse.py
# Creates schema + loads all facts and dimensions
```

### Step 6 — Connect Power BI
```
1. Open Power BI Desktop
2. Get Data → PostgreSQL Database
3. Server: localhost  |  Database: nigeria_energy_db
4. Import these views:
   - vw_disco_performance_monthly
   - vw_outage_saidi_saifi
   - vw_renewable_summary
5. Build visuals (see dashboard/POWERBI_SETUP.md for full guide)
```

---

## 📊 Key Metrics This Pipeline Surfaces

| Metric | Description | Regulatory Relevance |
|--------|-------------|---------------------|
| ATC&C Loss Rate | Aggregate Technical, Commercial & Collection losses | NERC minimum performance standard |
| SAIDI | System Average Interruption Duration Index (minutes/customer/year) | Distribution quality benchmark |
| SAIFI | System Average Interruption Frequency Index | QoS regulation metric |
| Collection Efficiency | Revenue actually collected vs. billed | DisCo financial viability |
| Tariff Band Compliance | Hours of supply per band vs. commitment | Customer protection enforcement |

---

## 💼 Business Impact

> *"Automated consolidation of Nigerian DisCo consumption data across 11 distribution companies and 36 states, reducing manual monthly aggregation from 3 days to under 15 minutes. The resulting warehouse enables regulators to enforce NERC QoS benchmarks with a 3x improvement in data granularity."*

**Applicable to:** NSERC, NERC, DisCo planning departments, NBET market monitoring

---

## 🛠️ Tools Used

| Tool | Purpose | Version |
|------|---------|---------|
| Python | ETL scripting | 3.11 |
| Pandas | Data transformation | 2.2.2 |
| SQLAlchemy | ORM / DB connection | 2.0.30 |
| PostgreSQL | Data warehouse | 15 |
| Azure Blob Storage | Raw file storage | — |
| Power BI Desktop | Dashboard & visualisation | Latest |
| Loguru | ETL logging | 0.7.2 |

---

## 📁 Data Dictionary

### fact_consumption (Primary fact table)
| Column | Type | Description |
|--------|------|-------------|
| energy_injected_mwh | NUMERIC | Total energy received from grid |
| energy_billed_mwh | NUMERIC | Energy for which customers were billed |
| system_loss_mwh | NUMERIC | Technical + commercial losses |
| atc_c_loss_pct | NUMERIC | Aggregate T&D + collection loss % |
| tariff_band | VARCHAR | NERC Band A–E classification |
| collection_efficiency_pct | NUMERIC | Revenue collection rate |

---

*Built by Ella — NSERC Portfolio | [LinkedIn](#) | [GitHub](#)*
