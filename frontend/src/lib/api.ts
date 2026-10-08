/**
 * src/lib/api.ts
 *
 * Typed API client for SolarPulse AI backend.
 * Reads the JWT from localStorage and attaches it as a Bearer token.
 */

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("solarpulse_access_token");
}

function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("solarpulse_refresh_token");
}

let isRefreshing = false;
let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;

  try {
    const res = await fetch(`${API_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    if (data.access_token) {
      localStorage.setItem("solarpulse_access_token", data.access_token);
      if (data.refresh_token) {
        localStorage.setItem("solarpulse_refresh_token", data.refresh_token);
      }
      return data.access_token as string;
    }
  } catch {
    return null;
  }
  return null;
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    if (res.status === 401 && typeof window !== "undefined") {
      // Try refresh token once
      if (!isRefreshing) {
        isRefreshing = true;
        refreshPromise = refreshAccessToken().finally(() => {
          isRefreshing = false;
          refreshPromise = null;
        });
      }
      const newToken = await refreshPromise;
      if (newToken) {
        headers["Authorization"] = `Bearer ${newToken}`;
        const retryRes = await fetch(`${API_URL}${path}`, { ...options, headers });
        if (retryRes.ok) {
          return retryRes.json() as Promise<T>;
        }
      }
      // If refresh failed, clear expired token and redirect to login
      localStorage.removeItem("solarpulse_access_token");
      localStorage.removeItem("solarpulse_refresh_token");
      localStorage.removeItem("solarpulse_user");
      window.location.href = "/login";
    }

    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail?.detail ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Plant {
  id: number;
  name: string;
  location: string | null;
  latitude: number;
  longitude: number;
  timezone: string;
  capacity_kw: number;
  inverter_capacity_kw: number;
  module_count: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PlantCreate {
  name: string;
  location?: string;
  latitude: number;
  longitude: number;
  timezone?: string;
  capacity_kw: number;
  inverter_capacity_kw: number;
  module_count?: number;
}

export interface PlantConfig {
  id: number;
  plant_id: number;
  tilt: number;
  azimuth: number;
  efficiency: number;
  soiling_threshold: number;
  clipping_threshold: number;
  forecast_horizon_minutes: number;
  created_at: string;
  updated_at: string;
}

export interface ForecastRecord {
  id: number;
  plant_id: number;
  forecast_time: string;
  generated_at: string;
  predicted_power_kw: number;
  actual_power_kw: number | null;
  confidence_lower: number | null;
  confidence_upper: number | null;
  model_name: string;
  model_version: string;
  physics_power_kw: number | null;
  ml_power_kw: number | null;
}

export interface ForecastSummary {
  plant_id: number;
  period_start: string;
  period_end: string;
  total_predicted_kwh: number;
  total_actual_kwh: number | null;
  mean_absolute_error_kw: number | null;
  record_count: number;
  model_name: string;
}

export interface ProbabilisticForecastPoint {
  forecast_time: string;
  p10_kw: number;
  p50_kw: number;
  p90_kw: number;
  uncertainty_band_kw: number;
  relative_uncertainty_pct: number;
  ramp_rate_kw_per_min: number;
  ramp_rate_pct_per_min: number;
  ramp_direction: "up" | "down" | "stable";
  ramp_risk_level: "low" | "medium" | "high" | "critical";
  cloud_impact_factor: number;
  bess_reserve_recommendation_kw: number;
  reserve_action: string;
}

export interface RampRiskSummary {
  max_ramp_rate_kw_per_min: number;
  max_ramp_down_kw_per_min: number;
  max_ramp_up_kw_per_min: number;
  ramp_risk_score: number;
  highest_risk_level: "low" | "medium" | "high" | "critical";
  high_risk_event_count: number;
  critical_risk_event_count: number;
  avg_uncertainty_band_kw: number;
  recommended_bess_capacity_kw: number;
  primary_action_advisory: string;
}

export interface ProbabilisticForecastResponse {
  plant_id: number;
  plant_name: string;
  capacity_kw: number;
  generated_at: string;
  horizon_minutes: number;
  interval_minutes: number;
  model_name: string;
  points: ProbabilisticForecastPoint[];
  summary: RampRiskSummary;
}

export interface Alert {
  id: number;
  plant_id: number;
  timestamp: string;
  alert_type: string;
  severity: string;
  message: string;
  expected_power_kw: number | null;
  actual_power_kw: number | null;
  deviation_percent: number | null;
  is_resolved: boolean;
  resolved_at: string | null;
  created_at: string;
}

<<<<<<< HEAD
export interface TechnicianStep {
  step_number: number;
  action: string;
  required_tools: string[];
  safety_note?: string | null;
}

export interface DiagnosisResponse {
  id?: number | null;
  plant_id: number;
  plant_name?: string | null;
  alert_id?: number | null;
  timestamp: string;
  root_cause_category: string;
  root_cause_title: string;
  confidence_score: number;
  inverter_error_code?: string | null;
  estimated_loss_kw: number;
  financial_impact_per_day: number;
  urgency_level: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | string;
  summary: string;
  root_cause_details: string;
  technician_steps: TechnicianStep[];
  safety_warning?: string | null;
  preventative_advice?: string | null;
  telemetry_evidence?: Record<string, unknown> | null;
  created_at: string;
}

export interface DiagnosisRequest {
  plant_id: number;
  alert_id?: number;
  inverter_error_code?: string;
  expected_power_kw?: number;
  actual_power_kw?: number;
  irradiance_w_m2?: number;
  temperature_c?: number;
  module_temp_c?: number;
  days_since_cleaning?: number;
  notes?: string;
}

export interface RootCauseTaxonomyItem {
  category: string;
  title: string;
  common_error_codes: string[];
  description: string;
  typical_urgency: string;
=======
export interface WeatherPoint {
  timestamp: string;
  temperature_c: number;
  humidity_pct: number;
  wind_speed_kph: number;
  cloud_cover_pct: number;
  uv_index: number;
  irradiance_w_m2: number;
  condition: string;
  is_day: boolean;
}

export interface WeatherData {
  latitude: number;
  longitude: number;
  location_name: string;
  timezone_id: string;
  fetched_at: string;
  source: string;
  current: WeatherPoint;
  hourly_forecast?: WeatherPoint[];
>>>>>>> 5b8d940ba41398923888f7d1dd960426e7782e02
}

// ── Plant endpoints ────────────────────────────────────────────────────────────

export const plantsApi = {
  list: () => apiFetch<Plant[]>("/api/v1/plants"),
  get: (id: number) => apiFetch<Plant>(`/api/v1/plants/${id}`),
  create: (data: PlantCreate) =>
    apiFetch<Plant>("/api/v1/plants", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getConfig: (id: number) => apiFetch<PlantConfig>(`/api/v1/plants/${id}/config`),
};

// ── Forecast endpoints ─────────────────────────────────────────────────────────

export const forecastApi = {
  list: (plantId: number, limit = 48) =>
    apiFetch<ForecastRecord[]>(
      `/api/v1/forecast/${plantId}?limit=${limit}`
    ),
  summary: (plantId: number) =>
    apiFetch<ForecastSummary>(`/api/v1/forecast/${plantId}/summary`),
  generate: (plantId: number, horizonMinutes = 60) =>
    apiFetch<ForecastRecord>(
      `/api/v1/forecast/${plantId}/generate?horizon_minutes=${horizonMinutes}`,
      { method: "POST" }
    ),
  getProbabilistic: (plantId: number, horizonMinutes = 240, intervalMinutes = 15) =>
    apiFetch<ProbabilisticForecastResponse>(
      `/api/v1/forecast/${plantId}/probabilistic?horizon_minutes=${horizonMinutes}&interval_minutes=${intervalMinutes}`
    ),
};

// ── Alert endpoints ────────────────────────────────────────────────────────────

export const alertsApi = {
  list: (plantId?: number, limit = 50) => {
    const qs = new URLSearchParams({ limit: String(limit) });
    if (plantId) qs.set("plant_id", String(plantId));
    return apiFetch<Alert[]>(`/api/v1/alerts?${qs}`);
  },
  resolve: (alertId: number) =>
    apiFetch<Alert>(`/api/v1/alerts/${alertId}/resolve`, {
      method: "PATCH",
    }),
};

<<<<<<< HEAD
// ── Diagnosis endpoints ────────────────────────────────────────────────────────

export const diagnosisApi = {
  getTaxonomy: () => apiFetch<RootCauseTaxonomyItem[]>("/api/v1/diagnosis/taxonomy"),
  diagnose: (data: DiagnosisRequest) =>
    apiFetch<DiagnosisResponse>("/api/v1/diagnosis/diagnose", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  diagnoseAlert: (alertId: number) =>
    apiFetch<DiagnosisResponse>(`/api/v1/diagnosis/alert/${alertId}`),
  listByPlant: (plantId: number, limit = 50) =>
    apiFetch<DiagnosisResponse[]>(`/api/v1/diagnosis/plant/${plantId}?limit=${limit}`),
=======
// ── Weather endpoints ──────────────────────────────────────────────────────────

export const weatherApi = {
  current: (plantId: number) =>
    apiFetch<WeatherData>(`/api/v1/weather/${plantId}/current`),
  forecast: (plantId: number, days = 3) =>
    apiFetch<WeatherData>(`/api/v1/weather/${plantId}/forecast?days=${days}`),
>>>>>>> 5b8d940ba41398923888f7d1dd960426e7782e02
};

// ── Auth helpers ───────────────────────────────────────────────────────────────

export function isLoggedIn(): boolean {
  return !!getToken();
}

export function logout(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem("solarpulse_access_token");
    localStorage.removeItem("solarpulse_refresh_token");
    localStorage.removeItem("solarpulse_user");
    window.location.href = "/login";
  }
}

export function getCurrentUser(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("solarpulse_user");
}
