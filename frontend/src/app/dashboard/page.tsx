"use client";

import Link from "next/link";
import { useEffect, useState, useCallback } from "react";
import {
  alertsApi,
  forecastApi,
  plantsApi,
  weatherApi,
  type Alert,
  type ForecastRecord,
  type Plant,
  type WeatherData,
} from "@/lib/api";

// ── Tiny SVG line chart ────────────────────────────────────────────────────────
function ForecastChart({ records }: { records: ForecastRecord[] }) {
  if (records.length < 2) {
    return (
      <div className="dash-empty" style={{ padding: "2rem 0" }}>
        No forecast data yet — trigger a forecast on a plant to see the chart.
      </div>
    );
  }

  const W = 800;
  const H = 200;
  const PAD = { top: 10, right: 16, bottom: 36, left: 52 };
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;

  const sorted = [...records].sort(
    (a, b) =>
      new Date(a.forecast_time).getTime() - new Date(b.forecast_time).getTime()
  );

  const values = sorted.map((r) => r.predicted_power_kw);
  const minV = Math.min(0, ...values);
  const maxV = Math.max(...values, 1);

  const xScale = (i: number) => PAD.left + (i / (sorted.length - 1)) * innerW;
  const yScale = (v: number) =>
    PAD.top + innerH - ((v - minV) / (maxV - minV)) * innerH;

  const predictedPath = sorted
    .map((r, i) => `${i === 0 ? "M" : "L"}${xScale(i)},${yScale(r.predicted_power_kw)}`)
    .join(" ");

  const actualPath = sorted
    .reduce<string[]>((acc, r, i) => {
      if (r.actual_power_kw != null) {
        acc.push(`${acc.length === 0 ? "M" : "L"}${xScale(i)},${yScale(r.actual_power_kw)}`);
      }
      return acc;
    }, [] as string[])
    .join(" ");

  // Filled area under predicted
  const firstX = xScale(0);
  const lastX = xScale(sorted.length - 1);
  const baseY = yScale(minV);
  const areaPath = `${predictedPath} L${lastX},${baseY} L${firstX},${baseY} Z`;

  // X-axis labels (up to 6)
  const step = Math.max(1, Math.floor(sorted.length / 6));
  const xLabels = sorted
    .filter((_, i) => i % step === 0 || i === sorted.length - 1)
    .map((r) => {
      const idx = sorted.indexOf(r);
      const d = new Date(r.forecast_time);
      const label = `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
      return { x: xScale(idx), label };
    });

  // Y-axis labels
  const yTicks = 4;
  const yLabels = Array.from({ length: yTicks + 1 }, (_, i) => {
    const v = minV + ((maxV - minV) * i) / yTicks;
    return { y: yScale(v), label: v.toFixed(0) };
  });

  return (
    <div className="dash-chart-wrap">
      <svg
        className="dash-chart-svg"
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--dash-accent)" stopOpacity="0.25" />
            <stop offset="100%" stopColor="var(--dash-accent)" stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {/* Grid lines */}
        {yLabels.map(({ y, label }) => (
          <g key={label}>
            <line
              x1={PAD.left}
              y1={y}
              x2={W - PAD.right}
              y2={y}
              stroke="rgba(255,255,255,0.06)"
              strokeWidth="1"
            />
            <text
              x={PAD.left - 6}
              y={y + 4}
              textAnchor="end"
              fontSize="10"
              fill="rgba(122,158,133,0.8)"
            >
              {label}
            </text>
          </g>
        ))}

        {/* X labels */}
        {xLabels.map(({ x, label }) => (
          <text
            key={label + x}
            x={x}
            y={H - 6}
            textAnchor="middle"
            fontSize="10"
            fill="rgba(122,158,133,0.8)"
          >
            {label}
          </text>
        ))}

        {/* Axes */}
        <line
          x1={PAD.left} y1={PAD.top} x2={PAD.left} y2={H - PAD.bottom}
          stroke="rgba(255,255,255,0.1)" strokeWidth="1"
        />
        <line
          x1={PAD.left} y1={H - PAD.bottom} x2={W - PAD.right} y2={H - PAD.bottom}
          stroke="rgba(255,255,255,0.1)" strokeWidth="1"
        />

        {/* Area fill */}
        <path d={areaPath} fill="url(#areaGrad)" />

        {/* Predicted line */}
        <path
          d={predictedPath}
          fill="none"
          stroke="var(--dash-accent)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Actual line */}
        {actualPath && (
          <path
            d={actualPath}
            fill="none"
            stroke="var(--dash-sun)"
            strokeWidth="1.5"
            strokeDasharray="4 3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}
      </svg>

      <div style={{ display: "flex", gap: "1.5rem", marginTop: "0.5rem" }}>
        <LegendDot color="var(--dash-accent)" label="Predicted (kW)" />
        <LegendDot color="var(--dash-sun)" label="Actual (kW)" dashed />
      </div>
    </div>
  );
}

function LegendDot({
  color,
  label,
  dashed,
}: {
  color: string;
  label: string;
  dashed?: boolean;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
      <svg width="20" height="10">
        <line
          x1="0"
          y1="5"
          x2="20"
          y2="5"
          stroke={color}
          strokeWidth="2"
          strokeDasharray={dashed ? "4 3" : "none"}
        />
      </svg>
      <span style={{ fontSize: "0.75rem", color: "var(--dash-muted)" }}>{label}</span>
    </div>
  );
}

// ── Weather widget ─────────────────────────────────────────────────────────────────────
function WeatherWidget({ weather }: { weather: WeatherData | null }) {
  if (!weather) {
    return (
      <div className="dash-card" style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        <div className="dash-card-title">🌤 Current Weather</div>
        <div className="dash-empty" style={{ padding: "1.5rem 0" }}>Loading weather…</div>
      </div>
    );
  }

  const c = weather.current;
  const isMock = weather.source === "mock";

  const statRow = (icon: string, label: string, value: string, color?: string) => (
    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.45rem 0", borderBottom: "1px solid var(--dash-border)" }}>
      <span style={{ fontSize: "1rem", width: "1.4rem", textAlign: "center", flexShrink: 0 }}>{icon}</span>
      <span style={{ fontSize: "0.78rem", color: "var(--dash-muted)", flex: 1 }}>{label}</span>
      <span style={{ fontSize: "0.88rem", fontWeight: 600, color: color ?? "var(--dash-text)" }}>{value}</span>
    </div>
  );

  return (
    <div className="dash-card" style={{ display: "flex", flexDirection: "column", gap: "0" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.75rem" }}>
        <div className="dash-card-title" style={{ margin: 0 }}>🌤 Current Weather</div>
        {isMock && (
          <span className="dash-badge dash-badge-muted" style={{ fontSize: "0.65rem" }}>mock</span>
        )}
      </div>

      <div style={{ marginBottom: "0.75rem" }}>
        <div style={{ fontSize: "1.65rem", fontWeight: 700, color: "var(--dash-sun)", lineHeight: 1 }}>
          {c.temperature_c.toFixed(1)}°C
        </div>
        <div style={{ fontSize: "0.8rem", color: "var(--dash-muted)", marginTop: "0.2rem" }}>
          {c.condition} • {weather.location_name}
        </div>
      </div>

      {statRow("☀️", "Irradiance", `${c.irradiance_w_m2.toFixed(0)} W/m²`, "var(--dash-sun)")}
      {statRow("💧", "Humidity", `${c.humidity_pct.toFixed(0)}%`)}
      {statRow("☁️", "Cloud Cover", `${c.cloud_cover_pct.toFixed(0)}%`)}
      {statRow("💨", "Wind", `${c.wind_speed_kph.toFixed(1)} km/h`)}
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.45rem 0" }}>
        <span style={{ fontSize: "1rem", width: "1.4rem", textAlign: "center", flexShrink: 0 }}>🔆</span>
        <span style={{ fontSize: "0.78rem", color: "var(--dash-muted)", flex: 1 }}>UV Index</span>
        <span style={{ fontSize: "0.88rem", fontWeight: 600, color: c.uv_index >= 6 ? "var(--dash-warning)" : "var(--dash-text)" }}>
          {c.uv_index.toFixed(1)}
        </span>
      </div>
    </div>
  );
}

// ── Alert row ─────────────────────────────────────────────────────────────────
function AlertRow({
  alert,
  onResolve,
}: {
  alert: Alert;
  onResolve: (id: number) => void;
}) {
  const severity = alert.severity as "CRITICAL" | "WARNING" | "INFO";
  const time = new Date(alert.timestamp).toLocaleString();

  return (
    <div className={`dash-alert-row ${severity}`}>
      <span className={`dash-alert-badge ${severity}`}>{severity}</span>
      <span className="dash-alert-msg">{alert.message}</span>
      <span className="dash-alert-time">{time}</span>
      {!alert.is_resolved && (
        <button
          className="dash-alert-resolve-btn"
          onClick={() => onResolve(alert.id)}
        >
          Resolve
        </button>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const [plants, setPlants] = useState<Plant[]>([]);
  const [forecasts, setForecasts] = useState<ForecastRecord[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [weather, setWeather] = useState<WeatherData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [p, a] = await Promise.all([plantsApi.list(), alertsApi.list(undefined, 20)]);
      setPlants(p);
      setAlerts(a);

      // Load forecasts and weather for the first plant if available
      if (p.length > 0) {
        const [fc, wx] = await Promise.all([
          forecastApi.list(p[0].id, 48),
          weatherApi.current(p[0].id).catch(() => null),
        ]);
        setForecasts(fc);
        setWeather(wx);
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to load dashboard data.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleResolve = async (id: number) => {
    try {
      await alertsApi.resolve(id);
      setAlerts((prev) =>
        prev.map((a) => (a.id === id ? { ...a, is_resolved: true } : a))
      );
    } catch {
      // ignore
    }
  };

  const activePlants = plants.filter((p) => p.is_active).length;
  const totalCapacity = plants.reduce((s, p) => s + p.capacity_kw, 0);
  const openAlerts = alerts.filter((a) => !a.is_resolved);
  const criticalAlerts = openAlerts.filter((a) => a.severity === "CRITICAL").length;

  return (
    <>
      <div style={{ marginBottom: "1.75rem" }}>
        <h1 className="dash-section-title" style={{ marginBottom: "0.25rem" }}>
          Overview
        </h1>
        <p style={{ color: "var(--dash-muted)", fontSize: "0.88rem" }}>
          Live status across all registered solar plants.
        </p>
      </div>

      {error && <div className="dash-error">⚠ {error}</div>}

      {loading ? (
        <div className="dash-loading">
          <div className="dash-spinner" />
          <div>Loading dashboard…</div>
        </div>
      ) : (
        <>
          {/* ── KPIs ── */}
          <div className="dash-kpi-grid">
            <div className="dash-kpi">
              <div className="dash-kpi-label">Active Plants</div>
              <div className="dash-kpi-value dash-kpi-accent">
                {activePlants}
                <span className="dash-kpi-unit">/ {plants.length}</span>
              </div>
              <div className="dash-kpi-sub">registered sites</div>
            </div>

            <div className="dash-kpi">
              <div className="dash-kpi-label">Total Capacity</div>
              <div className="dash-kpi-value dash-kpi-sun">
                {totalCapacity.toFixed(1)}
                <span className="dash-kpi-unit">kW</span>
              </div>
              <div className="dash-kpi-sub">across all plants</div>
            </div>

            <div className="dash-kpi">
              <div className="dash-kpi-label">Open Alerts</div>
              <div className={`dash-kpi-value ${criticalAlerts > 0 ? "dash-kpi-danger" : "dash-kpi-warning"}`}>
                {openAlerts.length}
              </div>
              <div className="dash-kpi-sub">
                {criticalAlerts} critical
              </div>
            </div>

            <div className="dash-kpi">
              <div className="dash-kpi-label">Forecast Records</div>
              <div className="dash-kpi-value">
                {forecasts.length}
              </div>
              <div className="dash-kpi-sub">
                {plants.length > 0 ? `for ${plants[0].name}` : "—"}
              </div>
            </div>
          </div>

          {/* ── Forecast chart + weather + alert sidebar ── */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 220px", gap: "1.25rem", marginBottom: "1.5rem" }}>
            {/* Left: chart */}
            <div className="dash-card">
              <div
                className="dash-card-title"
                style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}
              >
                <div>
                  Yield Forecast
                  {plants.length > 0 && (
                    <span style={{ marginLeft: "0.5rem", color: "var(--dash-accent)", textTransform: "none", letterSpacing: 0 }}>
                      — {plants[0].name}
                    </span>
                  )}
                </div>
                <Link
                  href="/dashboard/forecasts"
                  className="dash-btn dash-btn-ghost"
                  style={{
                    fontSize: "0.78rem",
                    padding: "0.2rem 0.55rem",
                    color: "var(--dash-sun)",
                    border: "1px solid rgba(240, 168, 50, 0.3)",
                  }}
                >
                  ⚡ P10/P50/P90 & Ramp Risk →
                </Link>
              </div>
              <ForecastChart records={forecasts} />
            </div>

            {/* Right: weather widget */}
            <WeatherWidget weather={weather} />
          </div>

          {/* ── Alert panel ── */}
          <div className="dash-card" style={{ marginBottom: "1.5rem" }}>
            <div className="dash-card-title">Recent Alerts</div>
            {openAlerts.length === 0 ? (
              <div className="dash-empty" style={{ padding: "1.5rem 0" }}>
                No open alerts 🎉
              </div>
            ) : (
              <div className="dash-alert-list">
                {openAlerts.slice(0, 6).map((a) => (
                  <AlertRow key={a.id} alert={a} onResolve={handleResolve} />
                ))}
              </div>
            )}
            {openAlerts.length > 6 && (
              <div style={{ marginTop: "0.75rem" }}>
                <Link href="/dashboard/alerts" className="dash-btn dash-btn-ghost" style={{ fontSize: "0.8rem" }}>
                  View all {openAlerts.length} alerts →
                </Link>
              </div>
            )}
          </div>

          {/* ── Plants ── */}
          <div style={{ marginBottom: "1rem", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <h2 className="dash-section-title" style={{ margin: 0 }}>
              Your Plants
            </h2>
            <Link href="/dashboard/plants/new" className="dash-btn dash-btn-primary">
              + Add Plant
            </Link>
          </div>

          {plants.length === 0 ? (
            <div className="dash-card dash-empty">
              <p>No plants registered yet.</p>
              <Link href="/dashboard/plants/new" className="dash-btn dash-btn-primary" style={{ marginTop: "1rem" }}>
                Register your first plant →
              </Link>
            </div>
          ) : (
            <div className="dash-plant-grid">
              {plants.map((plant) => (
                <Link
                  key={plant.id}
                  href={`/dashboard/plants/${plant.id}`}
                  className="dash-plant-card"
                >
                  <div className="dash-plant-name">
                    <span className={`dash-status-dot ${plant.is_active ? "dash-status-active" : "dash-status-inactive"}`} />
                    {plant.name}
                  </div>
                  <div className="dash-plant-loc">
                    {plant.location ?? `${plant.latitude.toFixed(3)}, ${plant.longitude.toFixed(3)}`}
                  </div>
                  <div className="dash-plant-stats">
                    <div>
                      <div className="dash-plant-stat-label">Capacity</div>
                      <div className="dash-plant-stat-value">{plant.capacity_kw} kW</div>
                    </div>
                    <div>
                      <div className="dash-plant-stat-label">Inverter</div>
                      <div className="dash-plant-stat-value">{plant.inverter_capacity_kw} kW</div>
                    </div>
                    {plant.module_count && (
                      <div>
                        <div className="dash-plant-stat-label">Modules</div>
                        <div className="dash-plant-stat-value">{plant.module_count}</div>
                      </div>
                    )}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </>
      )}
    </>
  );
}
