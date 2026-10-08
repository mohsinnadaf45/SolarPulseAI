-- ============================================================================
-- SolarPulse AI — TimescaleDB & PostgreSQL Schema Initialization
-- ============================================================================

-- Enable required PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "timescaledb" CASCADE;

-- ----------------------------------------------------------------------------
-- 1. Tenants & Multi-Tenancy
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tenants (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    slug        VARCHAR(100) UNIQUE NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ----------------------------------------------------------------------------
-- 2. Users & RBAC
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email       VARCHAR(255) UNIQUE NOT NULL,
    hashed_pw   VARCHAR(255) NOT NULL,
    full_name   VARCHAR(255),
    role        VARCHAR(32) NOT NULL DEFAULT 'viewer' CHECK (role IN ('viewer', 'operator', 'admin')),
    is_active   BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_users_tenant_id ON users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- ----------------------------------------------------------------------------
-- 3. Solar Plants & Plant Configuration
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS plants (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id          UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name               VARCHAR(255) NOT NULL,
    slug               VARCHAR(100) NOT NULL,
    latitude           DOUBLE PRECISION NOT NULL,
    longitude          DOUBLE PRECISION NOT NULL,
    altitude_m         DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    tilt_deg           DOUBLE PRECISION NOT NULL DEFAULT 25.0,
    azimuth_deg        DOUBLE PRECISION NOT NULL DEFAULT 180.0, -- 180 = South
    capacity_dc_kw     DOUBLE PRECISION NOT NULL,
    ac_export_limit_kw DOUBLE PRECISION NOT NULL,
    soiling_rate_daily DOUBLE PRECISION NOT NULL DEFAULT 0.002, -- 0.2% / dry day
    rain_wash_thresh_mm DOUBLE PRECISION NOT NULL DEFAULT 3.0,
    full_wash_thresh_mm DOUBLE PRECISION NOT NULL DEFAULT 12.0,
    alert_threshold_pct DOUBLE PRECISION NOT NULL DEFAULT 10.0,
    timezone           VARCHAR(64) NOT NULL DEFAULT 'UTC',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_tenant_plant_slug UNIQUE (tenant_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_plants_tenant_id ON plants(tenant_id);

-- ----------------------------------------------------------------------------
-- 4. SCADA Sensor Telemetry (TimescaleDB Hypertable)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scada_readings (
    time               TIMESTAMPTZ NOT NULL,
    plant_id           UUID NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
    active_power_kw    DOUBLE PRECISION,
    reactive_power_kvar DOUBLE PRECISION,
    ghi_sensor         DOUBLE PRECISION,
    dni_sensor         DOUBLE PRECISION,
    dhi_sensor         DOUBLE PRECISION,
    module_temp_c      DOUBLE PRECISION,
    ambient_temp_c     DOUBLE PRECISION,
    wind_speed_ms      DOUBLE PRECISION,
    inverter_status    SMALLINT DEFAULT 1, -- 1 = Running, 0 = Stopped, -1 = Fault
    PRIMARY KEY (time, plant_id)
);

-- Convert to TimescaleDB Hypertable partitioned by time (1-day chunk interval)
SELECT create_hypertable('scada_readings', 'time', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_scada_plant_time ON scada_readings (plant_id, time DESC);

-- ----------------------------------------------------------------------------
-- 5. Weather NWP Ingested Forecasts (TimescaleDB Hypertable)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS weather_raw (
    time               TIMESTAMPTZ NOT NULL,
    plant_id           UUID NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
    provider           VARCHAR(64) NOT NULL DEFAULT 'open-meteo',
    ghi_nwp            DOUBLE PRECISION,
    dni_nwp            DOUBLE PRECISION,
    dhi_nwp            DOUBLE PRECISION,
    temp_ambient_nwp   DOUBLE PRECISION,
    wind_speed_nwp     DOUBLE PRECISION,
    cloud_cover_pct    DOUBLE PRECISION,
    precipitation_mm   DOUBLE PRECISION DEFAULT 0.0,
    PRIMARY KEY (time, plant_id)
);

SELECT create_hypertable('weather_raw', 'time', chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_weather_plant_time ON weather_raw (plant_id, time DESC);

-- ----------------------------------------------------------------------------
-- 6. Computed Generation Forecasts (TimescaleDB Hypertable)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS forecasts (
    time               TIMESTAMPTZ NOT NULL,
    plant_id           UUID NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
    gross_dc_kw        DOUBLE PRECISION NOT NULL,
    clipped_kw         DOUBLE PRECISION NOT NULL,
    deliverable_kw     DOUBLE PRECISION NOT NULL,
    soiling_loss_pct   DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    clipping_loss_pct  DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    p10_kw             DOUBLE PRECISION,
    p50_kw             DOUBLE PRECISION,
    p90_kw             DOUBLE PRECISION,
    model_version      VARCHAR(32) NOT NULL DEFAULT '1.0.0',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (time, plant_id)
);

SELECT create_hypertable('forecasts', 'time', chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_forecasts_plant_time ON forecasts (plant_id, time DESC);

-- ----------------------------------------------------------------------------
-- 7. Anomaly Alerts
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS anomaly_alerts (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plant_id           UUID NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
    started_at         TIMESTAMPTZ NOT NULL,
    resolved_at        TIMESTAMPTZ,
    severity           VARCHAR(16) NOT NULL CHECK (severity IN ('critical', 'warning', 'info')),
    shortfall_pct      DOUBLE PRECISION NOT NULL,
    expected_kw        DOUBLE PRECISION NOT NULL,
    actual_kw          DOUBLE PRECISION NOT NULL,
    deficit_kwh        DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    consecutive_steps  INT NOT NULL DEFAULT 1,
    diagnostic_hint    TEXT,
    is_acknowledged    BOOLEAN NOT NULL DEFAULT false,
    acknowledged_by    UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_alerts_plant_started ON anomaly_alerts (plant_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON anomaly_alerts (severity);
CREATE INDEX IF NOT EXISTS idx_alerts_unresolved ON anomaly_alerts (plant_id) WHERE resolved_at IS NULL;

-- ----------------------------------------------------------------------------
-- 8. TimescaleDB Continuous Aggregates (Hourly rollups for chart performance)
-- ----------------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS scada_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    plant_id,
    avg(active_power_kw)       AS avg_power_kw,
    max(active_power_kw)       AS peak_power_kw,
    min(active_power_kw)       AS min_power_kw,
    avg(ghi_sensor)            AS avg_ghi,
    avg(module_temp_c)         AS avg_module_temp,
    count(*)                   AS reading_count
FROM scada_readings
GROUP BY bucket, plant_id
WITH NO DATA;

-- Enable automatic continuous aggregate refresh policies
SELECT add_continuous_aggregate_policy('scada_hourly',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '30 minutes',
    if_not_exists => TRUE
);

-- Hourly continuous aggregate for forecasts
CREATE MATERIALIZED VIEW IF NOT EXISTS forecasts_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    plant_id,
    avg(deliverable_kw)        AS avg_deliverable_kw,
    max(deliverable_kw)        AS peak_deliverable_kw,
    avg(gross_dc_kw)           AS avg_gross_dc_kw,
    avg(clipped_kw)            AS avg_clipped_kw,
    avg(p10_kw)                AS avg_p10_kw,
    avg(p50_kw)                AS avg_p50_kw,
    avg(p90_kw)                AS avg_p90_kw
FROM forecasts
GROUP BY bucket, plant_id
WITH NO DATA;

SELECT add_continuous_aggregate_policy('forecasts_hourly',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);
