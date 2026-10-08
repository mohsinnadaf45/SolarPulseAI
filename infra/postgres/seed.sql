-- ============================================================================
-- SolarPulse AI — Development Seed Data
-- ============================================================================

-- 1. Insert Default Tenant
INSERT INTO tenants (id, name, slug)
VALUES (
    'a0000000-0000-0000-0000-000000000001',
    'SolarPulse Energy Operations',
    'solarpulse-ops'
)
ON CONFLICT (id) DO NOTHING;

-- 2. Insert Standard Development Users
-- Default password for all seed accounts is: password123
-- (Bcrypt hash: $2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW)
INSERT INTO users (id, tenant_id, email, hashed_pw, full_name, role)
VALUES
(
    'u0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000001',
    'admin@solarpulse.ai',
    '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW',
    'System Administrator',
    'admin'
),
(
    'u0000000-0000-0000-0000-000000000002',
    'a0000000-0000-0000-0000-000000000001',
    'operator@solarpulse.ai',
    '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW',
    'Field Plant Operator',
    'operator'
),
(
    'u0000000-0000-0000-0000-000000000003',
    'a0000000-0000-0000-0000-000000000001',
    'viewer@solarpulse.ai',
    '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW',
    'Executive Analyst',
    'viewer'
)
ON CONFLICT (email) DO NOTHING;

-- 3. Insert Solar Plants
INSERT INTO plants (
    id, tenant_id, name, slug, latitude, longitude, altitude_m,
    tilt_deg, azimuth_deg, capacity_dc_kw, ac_export_limit_kw,
    soiling_rate_daily, rain_wash_thresh_mm, full_wash_thresh_mm,
    alert_threshold_pct, timezone
)
VALUES
(
    'b0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000001',
    'Bhadla Solar Complex Phase II',
    'bhadla-phase-2',
    27.5390,
    71.9170,
    210.0,
    26.0,
    180.0,
    1000.0,  -- 1.0 MW DC capacity
    850.0,   -- 850 kW Inverter AC cap
    0.0025,  -- Desert climate soiling rate (0.25%/day)
    3.0,
    12.0,
    10.0,
    'Asia/Kolkata'
),
(
    'b0000000-0000-0000-0000-000000000002',
    'a0000000-0000-0000-0000-000000000001',
    'Pavagada Solar Park Block 4',
    'pavagada-block-4',
    14.2810,
    77.4140,
    640.0,
    20.0,
    180.0,
    2500.0,  -- 2.5 MW DC capacity
    2000.0,  -- 2.0 MW Inverter AC cap
    0.0018,
    4.0,
    15.0,
    8.0,
    'Asia/Kolkata'
)
ON CONFLICT (id) DO NOTHING;

-- 4. Seed Time-Series Forecasts (Past 24 hours + Future 24 hours)
INSERT INTO forecasts (
    time, plant_id, gross_dc_kw, clipped_kw, deliverable_kw,
    soiling_loss_pct, clipping_loss_pct, p10_kw, p50_kw, p90_kw, model_version
)
SELECT
    t AS time,
    'b0000000-0000-0000-0000-000000000001'::uuid AS plant_id,
    -- Diurnal bell curve for DC gross power peaking at ~980 kW at solar noon (12:00)
    CASE
        WHEN EXTRACT(HOUR FROM t) BETWEEN 6 AND 18 THEN
            ROUND((980.0 * sin(pi() * (EXTRACT(HOUR FROM t) - 6) / 12.0))::numeric, 2)
        ELSE 0.0
    END AS gross_dc_kw,
    -- Clipped at 850 kW
    CASE
        WHEN EXTRACT(HOUR FROM t) BETWEEN 6 AND 18 THEN
            LEAST(850.0, ROUND((980.0 * sin(pi() * (EXTRACT(HOUR FROM t) - 6) / 12.0))::numeric, 2))
        ELSE 0.0
    END AS clipped_kw,
    -- Deliverable after 3% soiling derate
    CASE
        WHEN EXTRACT(HOUR FROM t) BETWEEN 6 AND 18 THEN
            ROUND((LEAST(850.0, 980.0 * sin(pi() * (EXTRACT(HOUR FROM t) - 6) / 12.0)) * 0.97)::numeric, 2)
        ELSE 0.0
    END AS deliverable_kw,
    3.0 AS soiling_loss_pct,
    CASE
        WHEN EXTRACT(HOUR FROM t) BETWEEN 10 AND 14 THEN 13.2
        ELSE 0.0
    END AS clipping_loss_pct,
    -- Quantile bands P10, P50, P90
    CASE
        WHEN EXTRACT(HOUR FROM t) BETWEEN 6 AND 18 THEN
            ROUND((LEAST(850.0, 980.0 * sin(pi() * (EXTRACT(HOUR FROM t) - 6) / 12.0)) * 0.88)::numeric, 2)
        ELSE 0.0
    END AS p10_kw,
    CASE
        WHEN EXTRACT(HOUR FROM t) BETWEEN 6 AND 18 THEN
            ROUND((LEAST(850.0, 980.0 * sin(pi() * (EXTRACT(HOUR FROM t) - 6) / 12.0)) * 0.97)::numeric, 2)
        ELSE 0.0
    END AS p50_kw,
    CASE
        WHEN EXTRACT(HOUR FROM t) BETWEEN 6 AND 18 THEN
            ROUND((LEAST(850.0, 980.0 * sin(pi() * (EXTRACT(HOUR FROM t) - 6) / 12.0)) * 1.02)::numeric, 2)
        ELSE 0.0
    END AS p90_kw,
    '1.0.0' AS model_version
FROM generate_series(
    now() - INTERVAL '24 hours',
    now() + INTERVAL '24 hours',
    INTERVAL '1 hour'
) AS t
ON CONFLICT (time, plant_id) DO NOTHING;

-- 5. Seed SCADA Readings (Past 24 hours up to current hour)
INSERT INTO scada_readings (
    time, plant_id, active_power_kw, reactive_power_kvar,
    ghi_sensor, dni_sensor, dhi_sensor, module_temp_c, ambient_temp_c,
    wind_speed_ms, inverter_status
)
SELECT
    t AS time,
    'b0000000-0000-0000-0000-000000000001'::uuid AS plant_id,
    -- Actual telemetry (slightly lower at 11:00-13:00 to simulate inverter string failure anomaly)
    CASE
        WHEN EXTRACT(HOUR FROM t) BETWEEN 11 AND 13 THEN
            ROUND((550.0 + random() * 30.0)::numeric, 2) -- Inverter defect shortfall!
        WHEN EXTRACT(HOUR FROM t) BETWEEN 6 AND 18 THEN
            ROUND((LEAST(850.0, 980.0 * sin(pi() * (EXTRACT(HOUR FROM t) - 6) / 12.0)) * 0.96 + (random() * 10 - 5))::numeric, 2)
        ELSE 0.0
    END AS active_power_kw,
    25.0 AS reactive_power_kvar,
    CASE
        WHEN EXTRACT(HOUR FROM t) BETWEEN 6 AND 18 THEN
            ROUND((950.0 * sin(pi() * (EXTRACT(HOUR FROM t) - 6) / 12.0))::numeric, 2)
        ELSE 0.0
    END AS ghi_sensor,
    800.0 AS dni_sensor,
    150.0 AS dhi_sensor,
    CASE
        WHEN EXTRACT(HOUR FROM t) BETWEEN 6 AND 18 THEN 45.0 + random() * 5.0
        ELSE 22.0
    END AS module_temp_c,
    32.0 AS ambient_temp_c,
    2.5 AS wind_speed_ms,
    1 AS inverter_status
FROM generate_series(
    now() - INTERVAL '24 hours',
    now(),
    INTERVAL '1 hour'
) AS t
ON CONFLICT (time, plant_id) DO NOTHING;

-- 6. Seed Sample Anomaly Alerts
INSERT INTO anomaly_alerts (
    id, plant_id, started_at, resolved_at, severity,
    shortfall_pct, expected_kw, actual_kw, deficit_kwh,
    consecutive_steps, diagnostic_hint, is_acknowledged
)
VALUES
(
    'c0000000-0000-0000-0000-000000000001',
    'b0000000-0000-0000-0000-000000000001',
    now() - INTERVAL '3 hours',
    NULL, -- Still active!
    'critical',
    32.4,
    824.5,
    557.0,
    802.5,
    3,
    'Sub-array string 3 current collapse detected; potential inverter MPPT tracking failure or localized string fuse blowout.',
    false
),
(
    'c0000000-0000-0000-0000-000000000002',
    'b0000000-0000-0000-0000-000000000001',
    now() - INTERVAL '20 hours',
    now() - INTERVAL '18 hours',
    'warning',
    14.2,
    650.0,
    557.7,
    184.6,
    2,
    'Elevated cell temperature (>52°C) causing thermal degradation loss exceeding baseline.',
    true
)
ON CONFLICT (id) DO NOTHING;
