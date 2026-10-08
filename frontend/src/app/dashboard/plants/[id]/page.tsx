"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import {
  alertsApi,
  forecastApi,
  plantsApi,
  type Alert,
  type ForecastRecord,
  type ForecastSummary,
  type Plant,
  type PlantConfig,
} from "@/lib/api";

// ── SVG Forecast chart (reused here) ──────────────────────────────────────────
function ForecastChart({ records }: { records: ForecastRecord[] }) {
  if (records.length < 2) {
    return (
      <div className="dash-empty" style={{ padding: "2rem 0" }}>
        No forecast data yet. Click &ldquo;Run Forecast&rdquo; above to generate one.
      </div>
    );
  }

  const W = 900;
  const H = 220;
  const PAD = { top: 12, right: 20, bottom: 38, left: 56 };
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;

  const sorted = [...records].sort(
    (a, b) =>
      new Date(a.forecast_time).getTime() - new Date(b.forecast_time).getTime()
  );

  const uppers = sorted.map((r) => r.confidence_upper ?? r.predicted_power_kw);
  const lowers = sorted.map((r) => r.confidence_lower ?? r.predicted_power_kw);
  const actuals = sorted.map((r) => r.actual_power_kw ?? null);
  const minV = Math.min(0, ...lowers);
  const maxV = Math.max(...uppers, 1);

  const xScale = (i: number) => PAD.left + (i / Math.max(1, sorted.length - 1)) * innerW;
  const yScale = (v: number) =>
    PAD.top + innerH - ((v - minV) / (maxV - minV)) * innerH;

  const predictedPath = sorted
    .map((r, i) => `${i === 0 ? "M" : "L"}${xScale(i)},${yScale(r.predicted_power_kw)}`)
    .join(" ");

  const upperPath = sorted
    .map((r, i) => `${i === 0 ? "M" : "L"}${xScale(i)},${yScale(r.confidence_upper ?? r.predicted_power_kw)}`)
    .join(" ");

  const lowerPath = sorted
    .map((r, i, arr) =>
      `${i === arr.length - 1 ? "M" : "L"}${xScale(arr.length - 1 - i)},${yScale(
        arr[arr.length - 1 - i].confidence_lower ?? arr[arr.length - 1 - i].predicted_power_kw
      )}`
    )
    .join(" ");

  const bandPath = upperPath + " " + lowerPath + " Z";

  const actualPath = sorted
    .reduce<string[]>((acc, r, i) => {
      if (r.actual_power_kw != null) {
        acc.push(`${acc.length === 0 ? "M" : "L"}${xScale(i)},${yScale(r.actual_power_kw)}`);
      }
      return acc;
    }, [])
    .join(" ");

  const step = Math.max(1, Math.floor(sorted.length / 7));
  const xLabels = sorted
    .map((r, i) => ({ r, i }))
    .filter(({ i }) => i % step === 0 || i === sorted.length - 1)
    .map(({ r, i }) => {
      const d = new Date(r.forecast_time);
      return {
        x: xScale(i),
        label: `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`,
      };
    });

  const yTicks = 5;
  const yLabels = Array.from({ length: yTicks + 1 }, (_, i) => {
    const v = minV + ((maxV - minV) * i) / yTicks;
    return { y: yScale(v), label: v.toFixed(0) };
  });

  return (
    <div className="dash-chart-wrap">
      <svg
        className="dash-chart-svg"
        style={{ height: 220 }}
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id="areaGrad2" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--dash-accent)" stopOpacity="0.3" />
            <stop offset="100%" stopColor="var(--dash-accent)" stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {yLabels.map(({ y, label }) => (
          <g key={label}>
            <line x1={PAD.left} y1={y} x2={W - PAD.right} y2={y}
              stroke="rgba(255,255,255,0.06)" strokeWidth="1" />
            <text x={PAD.left - 7} y={y + 4} textAnchor="end" fontSize="10"
              fill="rgba(122,158,133,0.8)">{label}</text>
          </g>
        ))}

        {xLabels.map(({ x, label }) => (
          <text key={label + x} x={x} y={H - 6} textAnchor="middle" fontSize="10"
            fill="rgba(122,158,133,0.8)">{label}</text>
        ))}

        <line x1={PAD.left} y1={PAD.top} x2={PAD.left} y2={H - PAD.bottom}
          stroke="rgba(255,255,255,0.1)" strokeWidth="1" />
        <line x1={PAD.left} y1={H - PAD.bottom} x2={W - PAD.right} y2={H - PAD.bottom}
          stroke="rgba(255,255,255,0.1)" strokeWidth="1" />

        {/* Confidence band */}
        <path d={bandPath} fill="rgba(61,189,110,0.1)" />

        {/* Predicted area fill */}
        <path
          d={`${predictedPath} L${xScale(sorted.length - 1)},${yScale(minV)} L${xScale(0)},${yScale(minV)} Z`}
          fill="url(#areaGrad2)"
        />

        {/* Predicted line */}
        <path d={predictedPath} fill="none" stroke="var(--dash-accent)"
          strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />

        {/* Actual line */}
        {actualPath && (
          <path d={actualPath} fill="none" stroke="var(--dash-sun)"
            strokeWidth="1.5" strokeDasharray="5 3" strokeLinecap="round" />
        )}
      </svg>

      <div style={{ display: "flex", gap: "1.5rem", marginTop: "0.5rem" }}>
        <LegendDot color="var(--dash-accent)" label="Predicted (kW)" />
        {actuals.some((a) => a !== null) && (
          <LegendDot color="var(--dash-sun)" label="Actual (kW)" dashed />
        )}
        <LegendDot color="rgba(61,189,110,0.5)" label="Confidence band" band />
      </div>
    </div>
  );
}

function LegendDot({
  color, label, dashed, band,
}: {
  color: string; label: string; dashed?: boolean; band?: boolean;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
      {band ? (
        <div style={{ width: 20, height: 10, background: color, borderRadius: 2 }} />
      ) : (
        <svg width="20" height="10">
          <line x1="0" y1="5" x2="20" y2="5" stroke={color} strokeWidth="2"
            strokeDasharray={dashed ? "5 3" : "none"} />
        </svg>
      )}
      <span style={{ fontSize: "0.75rem", color: "var(--dash-muted)" }}>{label}</span>
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function PlantDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const plantId = parseInt(id, 10);

  const [plant, setPlant] = useState<Plant | null>(null);
  const [config, setConfig] = useState<PlantConfig | null>(null);
  const [forecasts, setForecasts] = useState<ForecastRecord[]>([]);
  const [summary, setSummary] = useState<ForecastSummary | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [p, fc, sum, al] = await Promise.all([
        plantsApi.get(plantId),
        forecastApi.list(plantId, 48),
        forecastApi.summary(plantId).catch(() => null),
        alertsApi.list(plantId, 30),
      ]);
      setPlant(p);
      setForecasts(fc);
      setSummary(sum);
      setAlerts(al);

      const cfg = await plantsApi.getConfig(plantId).catch(() => null);
      setConfig(cfg);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load plant.");
    } finally {
      setLoading(false);
    }
  }, [plantId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const record = await forecastApi.generate(plantId);
      setForecasts((prev) => [record, ...prev].slice(0, 48));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Forecast failed.");
    } finally {
      setGenerating(false);
    }
  };

  const handleResolve = async (alertId: number) => {
    try {
      await alertsApi.resolve(alertId);
      setAlerts((prev) =>
        prev.map((a) => (a.id === alertId ? { ...a, is_resolved: true } : a))
      );
    } catch {
      // ignore
    }
  };

  if (loading) {
    return (
      <div className="dash-loading">
        <div className="dash-spinner" />
        <div>Loading plant…</div>
      </div>
    );
  }

  if (!plant) {
    return (
      <div className="dash-error">
        Plant not found.{" "}
        <Link href="/dashboard/plants" style={{ color: "var(--dash-accent)" }}>
          Back to plants
        </Link>
      </div>
    );
  }

  const openAlerts = alerts.filter((a) => !a.is_resolved);

  return (
    <>
      {/* Breadcrumb */}
      <div
        style={{ fontSize: "0.8rem", color: "var(--dash-muted)", marginBottom: "1.25rem" }}
      >
        <Link href="/dashboard/plants" style={{ color: "var(--dash-muted)", textDecoration: "none" }}>
          Plants
        </Link>
        <span style={{ margin: "0 0.4rem" }}>›</span>
        <span style={{ color: "var(--dash-text)" }}>{plant.name}</span>
      </div>

      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          marginBottom: "1.5rem",
          flexWrap: "wrap",
          gap: "1rem",
        }}
      >
        <div>
          <h1 className="dash-section-title" style={{ marginBottom: "0.25rem" }}>
            <span
              className={`dash-status-dot ${plant.is_active ? "dash-status-active" : "dash-status-inactive"}`}
            />
            {plant.name}
          </h1>
          <p style={{ color: "var(--dash-muted)", fontSize: "0.88rem" }}>
            {plant.location ?? `${plant.latitude}, ${plant.longitude}`} · {plant.timezone}
          </p>
        </div>

        <button
          className="dash-btn dash-btn-primary"
          onClick={handleGenerate}
          disabled={generating}
        >
          {generating ? "Generating…" : "▶ Run Forecast"}
        </button>
      </div>

      {error && <div className="dash-error">⚠ {error}</div>}

      {/* KPIs */}
      <div className="dash-kpi-grid" style={{ marginBottom: "1.5rem" }}>
        <div className="dash-kpi">
          <div className="dash-kpi-label">DC Capacity</div>
          <div className="dash-kpi-value dash-kpi-sun">
            {plant.capacity_kw}
            <span className="dash-kpi-unit">kW</span>
          </div>
        </div>
        <div className="dash-kpi">
          <div className="dash-kpi-label">Inverter Cap</div>
          <div className="dash-kpi-value">
            {plant.inverter_capacity_kw}
            <span className="dash-kpi-unit">kW</span>
          </div>
        </div>
        {summary && (
          <>
            <div className="dash-kpi">
              <div className="dash-kpi-label">Predicted Yield</div>
              <div className="dash-kpi-value dash-kpi-accent">
                {summary.total_predicted_kwh.toFixed(1)}
                <span className="dash-kpi-unit">kWh</span>
              </div>
            </div>
            {summary.mean_absolute_error_kw != null && (
              <div className="dash-kpi">
                <div className="dash-kpi-label">MAE</div>
                <div className="dash-kpi-value">
                  {summary.mean_absolute_error_kw.toFixed(2)}
                  <span className="dash-kpi-unit">kW</span>
                </div>
              </div>
            )}
          </>
        )}
        <div className="dash-kpi">
          <div className="dash-kpi-label">Open Alerts</div>
          <div
            className={`dash-kpi-value ${openAlerts.length > 0 ? "dash-kpi-danger" : "dash-kpi-accent"}`}
          >
            {openAlerts.length}
          </div>
        </div>
      </div>

      {/* Forecast Chart */}
      <div className="dash-card" style={{ marginBottom: "1.25rem" }}>
        <div className="dash-card-title">48-Hour Yield Forecast</div>
        <ForecastChart records={forecasts} />
      </div>

      <div className="dash-two-col">
        {/* Config card */}
        {config && (
          <div className="dash-card">
            <div className="dash-card-title">Plant Configuration</div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: "0.75rem 1.5rem",
              }}
            >
              {[
                { label: "Tilt", value: `${config.tilt}°` },
                { label: "Azimuth", value: `${config.azimuth}°` },
                { label: "Efficiency", value: `${(config.efficiency * 100).toFixed(1)}%` },
                { label: "Soiling Threshold", value: `${config.soiling_threshold}%` },
                { label: "Clipping Threshold", value: `${config.clipping_threshold}%` },
                { label: "Forecast Horizon", value: `${config.forecast_horizon_minutes} min` },
              ].map(({ label, value }) => (
                <div key={label}>
                  <div
                    style={{
                      fontSize: "0.7rem",
                      textTransform: "uppercase",
                      letterSpacing: "0.07em",
                      color: "var(--dash-muted)",
                      marginBottom: "0.2rem",
                    }}
                  >
                    {label}
                  </div>
                  <div style={{ fontWeight: 600 }}>{value}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Alerts */}
        <div className="dash-card">
          <div
            style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem" }}
          >
            <div className="dash-card-title" style={{ marginBottom: 0 }}>
              Alerts
            </div>
            <span className="dash-badge dash-badge-red">{openAlerts.length} open</span>
          </div>
          {alerts.length === 0 ? (
            <div className="dash-empty" style={{ padding: "1.5rem 0" }}>
              No alerts for this plant 🎉
            </div>
          ) : (
            <div className="dash-alert-list">
              {alerts.slice(0, 8).map((a) => (
                <div key={a.id} className={`dash-alert-row ${a.severity}`}>
                  <span className={`dash-alert-badge ${a.severity}`}>{a.severity}</span>
                  <span className="dash-alert-msg">{a.message}</span>
                  <span className="dash-alert-time">
                    {new Date(a.timestamp).toLocaleDateString()}
                  </span>
                  {!a.is_resolved ? (
                    <button
                      className="dash-alert-resolve-btn"
                      onClick={() => handleResolve(a.id)}
                    >
                      Resolve
                    </button>
                  ) : (
                    <span
                      style={{
                        fontSize: "0.7rem",
                        color: "var(--dash-accent)",
                        fontWeight: 600,
                      }}
                    >
                      ✓ Resolved
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
