# Solar Forecast API — Backend

A production-ready Python FastAPI backend for solar power plant forecasting, real-time SCADA monitoring, anomaly detection, and ML-based power prediction.

---

## What This Backend Does

| Feature | Description |
|---|---|
| **Solar Forecasting** | Physics + LightGBM ML pipeline |
| **SCADA Ingestion** | REST + WebSocket real-time data |
| **pvlib Physics** | Solar position, clearsky, POA irradiance |
| **Anomaly Detection** | Shortfall detection with configurable thresholds |
| **Soiling Loss** | Dynamic soiling-loss calculation |
| **Inverter Clipping** | AC export cap calculation |
| **Plant Management** | Full CRUD for plants and configurations |
| **JWT Auth** | OAuth2-compatible access + refresh tokens |
| **Alerts** | Severity-based alert persistence |
| **WebSocket** | Live SCADA stream per plant |
| **Predictive Maintenance** | Failure risk scoring, contributing factors & early warnings |
| **AI Plant Health Scoring** | Composite 0–100 plant health index & component breakdown |
| **Grid Curtailment** | Export cap curtailment prediction, energy loss & BESS opportunity |

---

## Architecture

```
backend/
├── app/
│   ├── api/
│   │   ├── v1/routes/     ← REST endpoints (auth, plants, forecast, anomaly, alerts)
│   │   ├── websockets/    ← SCADA WebSocket
│   │   └── deps.py        ← Shared FastAPI dependencies
│   ├── core/
│   │   ├── config.py      ← Pydantic Settings (env vars)
│   │   ├── database.py    ← Async SQLAlchemy engine + session
│   │   ├── security.py    ← JWT + password hashing
│   │   └── logging.py     ← Structured JSON logging
│   ├── models/            ← SQLAlchemy ORM models
│   ├── schemas/           ← Pydantic v2 request/response schemas
│   ├── services/          ← Business logic (forecast, anomaly, soiling, clipping, ...)
│   ├── workers/           ← Background tasks (physics, ML, ingestion, alert check)
│   └── main.py            ← FastAPI application factory
├── requirements.txt
├── .env.example
└── README.md
```

---

## Technologies

| Layer | Technology |
|---|---|
| Framework | FastAPI 0.115 |
| Database | PostgreSQL + asyncpg + SQLAlchemy 2.x async |
| Time-series | Compatible with TimescaleDB hypertables |
| Auth | JWT (python-jose) + bcrypt (passlib) |
| ML | LightGBM + pandas + numpy + scikit-learn |
| Physics | pvlib |
| Settings | pydantic-settings |

---

## Installation

### 1. Create and activate a virtual environment

Use **Python 3.11 or 3.12** if you can (simplest install). If you only have **Python 3.14**, install from the updated `requirements.txt` so pip pulls packages with prebuilt wheels—do not pin old versions of `scikit-learn` (1.5.x) or `pydantic` (2.9.x), or Windows will try to compile them and fail.

For **training only** on 3.14:

```bash
pip install -r requirements-ml.txt
python -m ml.training.train --plant-id P01 --dry-run
```

```bash
# Create
python -m venv .venv

# Activate — Windows
.venv\Scripts\activate

# Activate — Linux / macOS
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Environment Variables

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

| Variable | Description | Default |
|---|---|---|
| `APP_NAME` | API display name | `Solar Forecast API` |
| `APP_VERSION` | API version | `1.0.0` |
| `DEBUG` | Enable SQLAlchemy echo | `false` |
| `DATABASE_URL` | Async PostgreSQL connection string | `postgresql+asyncpg://...` |
| `JWT_SECRET_KEY` | **Change in production!** | — |
| `JWT_ALGORITHM` | JWT signing algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime | `7` |
| `CORS_ORIGINS` | Comma-separated allowed origins | `http://localhost:3000,...` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `ML_MODEL_PATH` | Path to LightGBM model file | `models/lightgbm_model.txt` |
| `NWP_API_URL` | Weather/NWP API URL (optional) | `` |
| `NWP_API_KEY` | Weather/NWP API key (optional) | `` |

> **Security**: Generate a strong JWT secret:
> ```bash
> python -c "import secrets; print(secrets.token_hex(64))"
> ```

---

## PostgreSQL Setup

```sql
-- Create the database
CREATE DATABASE solar_forecast;
```

### Create tables (development)

```bash
python -c "import asyncio; from app.core.database import init_db; asyncio.run(init_db())"
```

> Tables are **not** created automatically on every startup to prevent accidental data loss.

---

## Running the API

```bash
cd backend
uvicorn app.main:app --reload
```

With a custom host/port:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Swagger / API Documentation

| URL | Description |
|---|---|
| `http://localhost:8000/docs` | Interactive Swagger UI |
| `http://localhost:8000/redoc` | ReDoc documentation |
| `http://localhost:8000/openapi.json` | OpenAPI schema |

---

## Health Endpoint

```
GET /health
```

Response:
```json
{"status": "healthy", "version": "1.0.0"}
```

---

## Authentication

```
POST /api/v1/auth/register   — create a user (development)
POST /api/v1/auth/token      — login, get access + refresh tokens
POST /api/v1/auth/refresh    — refresh access token
```

All other endpoints require the header:
```
Authorization: Bearer <access_token>
```

---

## API Endpoints

### Plants
```
POST   /api/v1/plants
GET    /api/v1/plants
GET    /api/v1/plants/{plant_id}
PUT    /api/v1/plants/{plant_id}
DELETE /api/v1/plants/{plant_id}
GET    /api/v1/plants/{plant_id}/config
PUT    /api/v1/plants/{plant_id}/config
```

### Forecast
```
GET  /api/v1/forecast/{plant_id}
GET  /api/v1/forecast/{plant_id}/summary
POST /api/v1/forecast/{plant_id}/generate
```

### Anomaly
```
GET  /api/v1/anomaly/{plant_id}
POST /api/v1/anomaly/threshold
```

### Alerts
```
GET   /api/v1/alerts
GET   /api/v1/alerts/{alert_id}
PATCH /api/v1/alerts/{alert_id}/resolve
```

---

## WebSocket Endpoint

```
WS /ws/scada/{plant_id}
```

Streams the latest SCADA reading for the plant every 5 seconds as JSON.

Example message:
```json
{
  "plant_id": 1,
  "timestamp": "2024-01-15T10:30:00Z",
  "power_kw": 425.3,
  "irradiance_w_m2": 850.0,
  "temperature_c": 28.5,
  "_source": "database_poll_dev"
}
```

---

## ML Fallback Behaviour

If `ML_MODEL_PATH` does not point to a valid LightGBM model file:

- The API **does not crash**
- Forecasts are generated using a `development_fallback` model
- The `model_name` field in responses is set to `"development_fallback"` — **never falsely claims real ML**
- Replace the fallback by training a LightGBM model and placing it at `ML_MODEL_PATH`

---

## Development Mock Data

- **Weather data**: When `NWP_API_URL`/`NWP_API_KEY` are empty, the ingestion worker generates plausible mock SCADA readings
- **SCADA WebSocket**: Polls the database and sends real DB data with `"_source": "database_poll_dev"` marker
- **Notifications**: Alert notifications are logged instead of sent (no email/SMS required)

---

## Creating the First User

```bash
# Register via API
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "email": "admin@example.com", "password": "yourpassword"}'
```

> Restrict `/api/v1/auth/register` to admin-only in production.

---

## Enhancement 4 — Predictive Maintenance & Failure Forecasting

### Purpose
Identifies increasing failure risk for solar plant equipment (specifically inverters and balance-of-system stages) **before** physical breakdowns occur. Analyzes operational SCADA parameters, conversion efficiencies, thermal stress, and anomaly history.

### Inputs
- **SCADA Telemetry**: `power_kw`, `inverter_power_kw`, `expected_power_kw`, `module_temperature_c`, `temperature_c`, `irradiance_w_m2`.
- **Anomaly History**: Active and historical `AnomalyAlert` records (critical vs warning severities, shortfall deviations).
- **Plant Capacity / Config**: Nominal inverter conversion efficiency (default 96%), rated capacity.

### Risk Engine & ML Strategy
- **Inspection Finding**: No historical equipment failure or maintenance logs exist in the repository.
- **Transparent Operational Risk Engine**: Implemented via `OperationalRiskScorer` behind the abstract `FailureRiskPredictorBase` interface.
  - *Thermal Stress Score (0–100)*: Evaluates module temperature against critical thresholds (65°C) and delta above ambient.
  - *Efficiency Derate Score (0–100)*: Measures observed conversion efficiency drop relative to nominal (0.96).
  - *Shortfall Persistence Score (0–100)*: Evaluates frequency and severity of unexpected generation deficits (>10%).
  - *Anomaly Severity Score (0–100)*: Weighted penalty for active unresolved critical (30 pts) and warning (15 pts) alerts.
- **Classification**:
  - `0 – 29`: **LOW**
  - `30 – 59`: **MEDIUM**
  - `60 – 79`: **HIGH**
  - `80 – 100`: **CRITICAL**
- **Safety / Decision Support**: Never claims confirmed physical diagnosis. Outputs probabilities, risk tiers, and specific early warnings and inspection steps.

### Endpoints
```
POST /api/v1/maintenance/assess               — calculate/persist failure risk assessment
GET  /api/v1/maintenance/{plant_id}          — retrieve equipment risk assessments
GET  /api/v1/maintenance/high-risk/list      — list equipment with HIGH/CRITICAL failure risk
GET  /api/v1/maintenance/{plant_id}/recommendations — actionable maintenance recommendations
```

---

## Enhancement 5 — AI-Based Solar Plant Health Scoring

### Purpose
Calculates a holistic 0–100 operational health index summarizing plant condition across 5 core dimensions:
1. **Generation Performance (30%)**: Expected vs actual generation yield ratio.
2. **Inverter Health (20%)**: Conversion efficiency stability and power tracking.
3. **Soiling Condition (15%)**: Dynamic soiling derate from `soiling_service`.
4. **Anomaly Health (20%)**: Deductions based on active unresolved anomaly alerts.
5. **Equipment Health (15%)**: Inverse of predictive maintenance failure risk score from Enhancement 4.

### Missing Data Handling
If any optional sensor data stream is missing, weights are **dynamically renormalized** across available components so plants are never unfairly penalized.

### Health Status Classification
- `90 – 100`: **EXCELLENT**
- `75 – 89`:  **GOOD**
- `60 – 74`:  **NEEDS ATTENTION**
- `40 – 59`:  **POOR**
- `0 – 39`:   **CRITICAL**

### Endpoints
```
GET  /api/v1/health-score/{plant_id}            — current plant health score and status
POST /api/v1/health-score/{plant_id}/calculate  — trigger on-demand calculation
GET  /api/v1/health-score/{plant_id}/components — retrieve component score breakdown
GET  /api/v1/health-score/{plant_id}/history    — historical health scores for trend analysis
```

---

## Enhancement 6 — Grid Curtailment Prediction & Optimization

### Purpose
Predicts when forecasted solar generation will exceed AC grid export capacity, calculates potential active power curtailment (kW) and energy loss (kWh), determines risk level, and provides intelligent decision support recommendations.

### Key Calculations
- $\text{potential\_curtailment\_kw} = \max(0, \text{forecast\_generation\_kw} - \text{export\_limit\_kw})$
- $\text{potential\_curtailment\_kwh} = \text{potential\_curtailment\_kw} \times \Delta t_{\text{hours}}$
- $\text{curtailment\_percentage} = (\text{curtailed\_kw} / \text{forecast\_kw}) \times 100$

### Risk Levels
- **LOW**: Curtailment percentage < 5% or 0 kW.
- **MEDIUM**: 5% $\le$ Curtailment percentage < 20%.
- **HIGH**: Curtailment percentage $\ge$ 20%.

### Decision Support & BESS Opportunity
- Recommends optimal battery energy storage system (BESS) charging windows and power absorption ratings to capture surplus energy without export penalties.
- Decision support only; never controls grid hardware directly.

### Endpoints
```
GET  /api/v1/curtailment/{plant_id}          — retrieve curtailment prediction
POST /api/v1/curtailment/predict             — predict curtailment with custom export limit/horizon
GET  /api/v1/curtailment/{plant_id}/history  — historical curtailment records
```

---

## Running Backend Tests

```bash
# Run entire test suite (47 tests)
python -m pytest -v

# Run enhancement tests specifically (20 tests)
python -m pytest tests/test_enhancements.py -v
```
