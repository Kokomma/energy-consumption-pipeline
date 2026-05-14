-- ============================================================
-- NSERC Energy Data Warehouse — Star Schema DDL
-- Project: DE-001 | Energy Consumption Pipeline
-- Author: Ella | NSERC Portfolio
-- ============================================================
-- Compatible with: PostgreSQL 15+, Azure SQL Database
-- ============================================================

-- ─────────────────────────────────────────────
-- DIMENSION TABLES
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS dim_date (
    date_key        SERIAL PRIMARY KEY,
    full_date       DATE NOT NULL UNIQUE,
    year            SMALLINT NOT NULL,
    quarter         SMALLINT NOT NULL,
    quarter_label   VARCHAR(10) NOT NULL,   -- e.g. "Q1 2023"
    month           SMALLINT NOT NULL,
    month_name      VARCHAR(15) NOT NULL,
    day_of_month    SMALLINT NOT NULL,
    day_of_week     VARCHAR(10) NOT NULL,
    is_weekend      BOOLEAN NOT NULL DEFAULT FALSE,
    fiscal_year     SMALLINT NOT NULL       -- Nigeria FY: Jan-Dec
);

CREATE TABLE IF NOT EXISTS dim_disco (
    disco_key       SERIAL PRIMARY KEY,
    disco_name      VARCHAR(60) NOT NULL UNIQUE,
    region          VARCHAR(30) NOT NULL,
    headquarters    VARCHAR(60),
    states_covered  TEXT,                   -- comma-separated
    privatised_year SMALLINT,
    license_number  VARCHAR(30),
    is_active       BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS dim_customer_class (
    class_key       SERIAL PRIMARY KEY,
    class_name      VARCHAR(40) NOT NULL UNIQUE,
    voltage_level   CHAR(2) NOT NULL CHECK (voltage_level IN ('LV', 'HV')),
    description     TEXT,
    typical_load_kw NUMERIC(10,2)
);

CREATE TABLE IF NOT EXISTS dim_tariff_band (
    band_key        SERIAL PRIMARY KEY,
    band_name       VARCHAR(10) NOT NULL UNIQUE,  -- Band A–E
    min_hours       NUMERIC(4,1) NOT NULL,
    max_hours       NUMERIC(4,1) NOT NULL,
    description     VARCHAR(80)
);

CREATE TABLE IF NOT EXISTS dim_renewable_type (
    type_key        SERIAL PRIMARY KEY,
    type_name       VARCHAR(30) NOT NULL UNIQUE,
    category        VARCHAR(30),  -- Solar, Hydro, Wind, Biomass
    emission_factor_kg_co2_kwh NUMERIC(6,4)
);

-- ─────────────────────────────────────────────
-- FACT TABLES
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS fact_consumption (
    consumption_key     BIGSERIAL PRIMARY KEY,
    date_key            INT REFERENCES dim_date(date_key),
    disco_key           INT REFERENCES dim_disco(disco_key),
    class_key           INT REFERENCES dim_customer_class(class_key),
    band_key            INT REFERENCES dim_tariff_band(band_key),

    -- Volume metrics (MWh)
    energy_injected_mwh     NUMERIC(12,2) NOT NULL,
    energy_billed_mwh       NUMERIC(12,2) NOT NULL,
    system_loss_mwh         NUMERIC(12,2) NOT NULL,

    -- Performance indicators
    loss_rate_pct           NUMERIC(6,2),
    atc_c_loss_pct          NUMERIC(6,2),
    hours_of_supply         NUMERIC(4,1),
    collection_efficiency_pct NUMERIC(6,2),

    -- Financial metrics
    tariff_rate_ngn_kwh     NUMERIC(8,2),
    revenue_ngn_millions    NUMERIC(12,2),
    revenue_collected_ngn_m NUMERIC(12,2),

    -- Customer metrics
    customer_count          INT,
    energy_per_customer_kwh NUMERIC(10,2),

    -- Metadata
    state                   VARCHAR(40),
    region                  VARCHAR(30),
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fact_outages (
    outage_key          BIGSERIAL PRIMARY KEY,
    outage_id           VARCHAR(20) UNIQUE NOT NULL,
    date_key            INT REFERENCES dim_date(date_key),
    disco_key           INT REFERENCES dim_disco(disco_key),

    -- Time metrics
    start_datetime      TIMESTAMP NOT NULL,
    end_datetime        TIMESTAMP,
    duration_hours      NUMERIC(8,2),
    response_time_hrs   NUMERIC(6,2),

    -- Impact metrics
    customers_affected  INT,
    mwh_lost            NUMERIC(10,2),
    saidi_minutes       NUMERIC(12,0),   -- System Average Interruption Duration Index
    saifi_events        INT DEFAULT 1,   -- System Average Interruption Frequency Index

    -- Classification
    cause_category      VARCHAR(50),
    cause_grouped       VARCHAR(30),
    severity            VARCHAR(10),
    affected_state      VARCHAR(40),
    fault_location      VARCHAR(120),
    resolved            BOOLEAN DEFAULT FALSE,

    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fact_renewable (
    renewable_key           BIGSERIAL PRIMARY KEY,
    date_key                INT REFERENCES dim_date(date_key),
    type_key                INT REFERENCES dim_renewable_type(type_key),

    state                   VARCHAR(40),
    installed_capacity_mw   NUMERIC(10,2),
    generation_mwh          NUMERIC(12,2),
    capacity_factor_pct     NUMERIC(6,2),
    grid_share_pct          NUMERIC(8,4),
    co2_avoided_tonnes      NUMERIC(12,2),
    project_count           INT,
    investment_usd_millions NUMERIC(12,2),
    lcoe_estimate_usd_mwh   NUMERIC(8,2),

    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─────────────────────────────────────────────
-- PERFORMANCE INDEXES
-- ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_fact_consumption_date     ON fact_consumption(date_key);
CREATE INDEX IF NOT EXISTS idx_fact_consumption_disco    ON fact_consumption(disco_key);
CREATE INDEX IF NOT EXISTS idx_fact_outages_date         ON fact_outages(date_key);
CREATE INDEX IF NOT EXISTS idx_fact_outages_disco        ON fact_outages(disco_key);
CREATE INDEX IF NOT EXISTS idx_fact_outages_severity     ON fact_outages(severity);
CREATE INDEX IF NOT EXISTS idx_fact_renewable_date       ON fact_renewable(date_key);

-- ─────────────────────────────────────────────
-- ANALYTICAL VIEWS
-- ─────────────────────────────────────────────

CREATE OR REPLACE VIEW vw_disco_performance_monthly AS
SELECT
    d.full_date,
    d.year,
    d.month_name,
    d.quarter_label,
    disco.disco_name,
    disco.region,
    SUM(fc.energy_injected_mwh)          AS total_energy_injected_mwh,
    SUM(fc.energy_billed_mwh)            AS total_energy_billed_mwh,
    AVG(fc.loss_rate_pct)                AS avg_loss_rate_pct,
    SUM(fc.revenue_ngn_millions)         AS gross_revenue_ngn_m,
    SUM(fc.revenue_collected_ngn_m)      AS collected_revenue_ngn_m,
    AVG(fc.collection_efficiency_pct)    AS avg_collection_efficiency,
    SUM(fc.customer_count)               AS total_customers,
    AVG(fc.hours_of_supply)              AS avg_hours_of_supply
FROM fact_consumption fc
JOIN dim_date d        ON fc.date_key  = d.date_key
JOIN dim_disco disco   ON fc.disco_key = disco.disco_key
GROUP BY d.full_date, d.year, d.month_name, d.quarter_label, disco.disco_name, disco.region;


CREATE OR REPLACE VIEW vw_outage_saidi_saifi AS
SELECT
    d.year,
    d.month_name,
    disco.disco_name,
    disco.region,
    COUNT(fo.outage_key)                 AS total_outages,
    SUM(fo.saidi_minutes)                AS total_saidi_minutes,
    SUM(fo.saifi_events)                 AS total_saifi_events,
    AVG(fo.duration_hours)               AS avg_duration_hours,
    SUM(fo.customers_affected)           AS total_customers_affected,
    SUM(fo.mwh_lost)                     AS total_mwh_lost,
    AVG(fo.response_time_hrs)            AS avg_response_time_hrs
FROM fact_outages fo
JOIN dim_date d        ON fo.date_key  = d.date_key
JOIN dim_disco disco   ON fo.disco_key = disco.disco_key
GROUP BY d.year, d.month_name, disco.disco_name, disco.region;


CREATE OR REPLACE VIEW vw_renewable_summary AS
SELECT
    d.year,
    d.month_name,
    rt.type_name                         AS renewable_type,
    fr.state,
    SUM(fr.installed_capacity_mw)        AS total_capacity_mw,
    SUM(fr.generation_mwh)               AS total_generation_mwh,
    AVG(fr.capacity_factor_pct)          AS avg_capacity_factor_pct,
    SUM(fr.co2_avoided_tonnes)           AS total_co2_avoided,
    SUM(fr.project_count)                AS total_projects,
    SUM(fr.investment_usd_millions)      AS total_investment_usd_m
FROM fact_renewable fr
JOIN dim_date d                ON fr.date_key  = d.date_key
JOIN dim_renewable_type rt     ON fr.type_key  = rt.type_key
GROUP BY d.year, d.month_name, rt.type_name, fr.state;

-- ─────────────────────────────────────────────
-- SEED: Dimension Data
-- ─────────────────────────────────────────────

INSERT INTO dim_tariff_band (band_name, min_hours, max_hours, description) VALUES
('Band A', 20, 24, 'Minimum 20 hours supply per day'),
('Band B', 16, 20, 'Minimum 16 hours supply per day'),
('Band C', 12, 16, 'Minimum 12 hours supply per day'),
('Band D',  8, 12, 'Minimum 8 hours supply per day'),
('Band E',  0,  8, 'Below 8 hours supply per day')
ON CONFLICT DO NOTHING;

INSERT INTO dim_customer_class (class_name, voltage_level, description, typical_load_kw) VALUES
('Residential_LV',  'LV', 'Residential customers on low voltage',       2.5),
('Commercial_LV',   'LV', 'Commercial customers on low voltage',        15.0),
('Industrial_HV',   'HV', 'Industrial customers on high voltage',      500.0),
('Special_Load_HV', 'HV', 'Special loads e.g. telecom, govt, airports',200.0)
ON CONFLICT DO NOTHING;

INSERT INTO dim_renewable_type (type_name, category, emission_factor_kg_co2_kwh) VALUES
('Solar_PV',    'Solar',  0.0),
('Small_Hydro', 'Hydro',  0.004),
('Wind',        'Wind',   0.0),
('Biomass',     'Biomass',0.23)
ON CONFLICT DO NOTHING;
