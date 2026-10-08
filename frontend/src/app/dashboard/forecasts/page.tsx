"use client";

import { useCallback, useEffect, useState } from "react";
import {
  forecastApi,
  plantsApi,
  type ForecastRecord,
  type Plant,
  type ProbabilisticForecastResponse,
} from "@/lib/api";
import ProbabilisticBandChart from "@/components/forecast/ProbabilisticBandChart";

export default function ForecastsPage() {
  const [plants, setPlants] = useState<Plant[]>([]);
  const [selectedPlantId, setSelectedPlantId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<"probabilistic" | "history">("probabilistic");

  // Probabilistic state
  const [horizonMinutes, setHorizonMinutes] = useState<number>(240);
  const [intervalMinutes, setIntervalMinutes] = useState<number>(15);
  const [probData, setProbData] = useState<ProbabilisticForecastResponse | null>(null);
  const [loadingProb, setLoadingProb] = useState(false);
  const [filterCriticalOnly, setFilterCriticalOnly] = useState(false);

  // Point history state
  const [forecasts, setForecasts] = useState<ForecastRecord[]>([]);
  const [loadingPlants, setLoadingPlants] = useState(true);
  const [loadingFc, setLoadingFc] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const data = await plantsApi.list();
        setPlants(data);
        if (data.length > 0) setSelectedPlantId(data[0].id);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to load plants.");
      } finally {
        setLoadingPlants(false);
      }
    })();
  }, []);

  const loadProbabilistic = useCallback(
    async (plantId: number, horizon: number, interval: number) => {
      setLoadingProb(true);
      setError(null);
      try {
        const data = await forecastApi.getProbabilistic(plantId, horizon, interval);
        setProbData(data);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to load probabilistic forecast.");
      } finally {
        setLoadingProb(false);
      }
    },
    []
  );

  const loadForecasts = useCallback(async (plantId: number) => {
    setLoadingFc(true);
    setError(null);
    try {
      const data = await forecastApi.list(plantId, 100);
      setForecasts(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load historical forecasts.");
    } finally {
      setLoadingFc(false);
    }
  }, []);

  useEffect(() => {
    if (selectedPlantId != null) {
      if (activeTab === "probabilistic") {
        loadProbabilistic(selectedPlantId, horizonMinutes, intervalMinutes);
      } else {
        loadForecasts(selectedPlantId);
      }
    }
  }, [selectedPlantId, activeTab, horizonMinutes, intervalMinutes, loadProbabilistic, loadForecasts]);

  const handleGenerate = async () => {
    if (!selectedPlantId) return;
    setGenerating(true);
    setError(null);
    try {
      const record = await forecastApi.generate(selectedPlantId);
      setForecasts((prev) => [record, ...prev]);
      if (activeTab === "probabilistic") {
        loadProbabilistic(selectedPlantId, horizonMinutes, intervalMinutes);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Forecast generation failed.");
    } finally {
      setGenerating(false);
    }
  };

  const selectedPlant = plants.find((p) => p.id === selectedPlantId);

  const sortedForecasts = [...forecasts].sort(
    (a, b) => new Date(b.forecast_time).getTime() - new Date(a.forecast_time).getTime()
  );

  const displayedPoints = probData?.points.filter((pt) =>
    filterCriticalOnly ? pt.ramp_risk_level === "high" || pt.ramp_risk_level === "critical" : true
  ) || [];

  const getRiskColor = (level?: string) => {
    switch (level) {
      case "critical":
        return "#e85252";
      case "high":
        return "#f0a832";
      case "medium":
        return "#3dbd6e";
      default:
        return "var(--dash-muted)";
    }
  };

  return (
    <>
      {/* Header */}
      <div style={{ marginBottom: "1.5rem" }}>
        <h1 className="dash-section-title" style={{ marginBottom: "0.25rem" }}>
          Forecast & Risk Intelligence
        </h1>
        <p style={{ color: "var(--dash-muted)", fontSize: "0.88rem" }}>
          Probabilistic quantile forecasting (P10 / P50 / P90), rapid cloud-passage detection, and dynamic BESS reserve dispatch.
        </p>
      </div>

      {error && <div className="dash-error" style={{ marginBottom: "1.25rem" }}>⚠ {error}</div>}

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          gap: "0.5rem",
          borderBottom: "1px solid var(--dash-border)",
          marginBottom: "1.5rem",
        }}
      >
        <button
          type="button"
          onClick={() => setActiveTab("probabilistic")}
          style={{
            background: "none",
            border: "none",
            padding: "0.6rem 1.25rem",
            cursor: "pointer",
            fontWeight: 600,
            fontSize: "0.9rem",
            color: activeTab === "probabilistic" ? "var(--dash-accent)" : "var(--dash-muted)",
            borderBottom: activeTab === "probabilistic" ? "2px solid var(--dash-accent)" : "2px solid transparent",
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
          }}
        >
          <span>🌤️</span> Probabilistic & Ramp Risk
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("history")}
          style={{
            background: "none",
            border: "none",
            padding: "0.6rem 1.25rem",
            cursor: "pointer",
            fontWeight: 600,
            fontSize: "0.9rem",
            color: activeTab === "history" ? "var(--dash-accent)" : "var(--dash-muted)",
            borderBottom: activeTab === "history" ? "2px solid var(--dash-accent)" : "2px solid transparent",
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
          }}
        >
          <span>📜</span> Point Forecast History
        </button>
      </div>

      {/* Controls Bar */}
      <div
        style={{
          display: "flex",
          gap: "0.85rem",
          alignItems: "center",
          marginBottom: "1.5rem",
          flexWrap: "wrap",
          background: "var(--dash-card)",
          padding: "0.85rem 1rem",
          borderRadius: 8,
          border: "1px solid var(--dash-border)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <label htmlFor="forecast-plant-select" style={{ fontSize: "0.82rem", color: "var(--dash-muted)" }}>
            Plant:
          </label>
          {loadingPlants ? (
            <span style={{ color: "var(--dash-muted)", fontSize: "0.85rem" }}>Loading…</span>
          ) : (
            <select
              id="forecast-plant-select"
              className="dash-input"
              style={{ minWidth: 200, padding: "0.45rem 0.65rem" }}
              value={selectedPlantId ?? ""}
              onChange={(e) => setSelectedPlantId(parseInt(e.target.value, 10))}
            >
              {plants.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.capacity_kw} kW)
                </option>
              ))}
            </select>
          )}
        </div>

        {activeTab === "probabilistic" && (
          <>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <label htmlFor="forecast-horizon-select" style={{ fontSize: "0.82rem", color: "var(--dash-muted)" }}>
                Horizon:
              </label>
              <select
                id="forecast-horizon-select"
                className="dash-input"
                style={{ padding: "0.45rem 0.65rem" }}
                value={horizonMinutes}
                onChange={(e) => setHorizonMinutes(parseInt(e.target.value, 10))}
              >
                <option value={120}>2 Hours</option>
                <option value={240}>4 Hours (Standard)</option>
                <option value={480}>8 Hours</option>
                <option value={720}>12 Hours</option>
                <option value={1440}>24 Hours (Full Day)</option>
              </select>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <label htmlFor="forecast-step-select" style={{ fontSize: "0.82rem", color: "var(--dash-muted)" }}>
                Interval:
              </label>
              <select
                id="forecast-step-select"
                className="dash-input"
                style={{ padding: "0.45rem 0.65rem" }}
                value={intervalMinutes}
                onChange={(e) => setIntervalMinutes(parseInt(e.target.value, 10))}
              >
                <option value={15}>15 Minutes</option>
                <option value={30}>30 Minutes</option>
                <option value={60}>60 Minutes</option>
              </select>
            </div>
          </>
        )}

        <div style={{ marginLeft: "auto", display: "flex", gap: "0.5rem" }}>
          {activeTab === "probabilistic" ? (
            <button
              className="dash-btn dash-btn-primary"
              onClick={() =>
                selectedPlantId && loadProbabilistic(selectedPlantId, horizonMinutes, intervalMinutes)
              }
              disabled={loadingProb || !selectedPlantId}
            >
              {loadingProb ? "Refreshing…" : "🔄 Refresh Risk Profile"}
            </button>
          ) : (
            <button
              className="dash-btn dash-btn-primary"
              onClick={handleGenerate}
              disabled={generating || !selectedPlantId}
            >
              {generating ? "Generating…" : "▶ Generate Point Forecast"}
            </button>
          )}
        </div>
      </div>

      {/* ── TAB 1: Probabilistic & Ramp Risk ────────────────────────────────────────── */}
      {activeTab === "probabilistic" && (
        <>
          {loadingProb ? (
            <div className="dash-loading" style={{ padding: "4rem 0" }}>
              <div className="dash-spinner" />
              <div>Calculating probabilistic quantiles & ramp risk vectors…</div>
            </div>
          ) : !probData ? (
            <div className="dash-card dash-empty">
              Select a plant to compute probabilistic forecasts and ramp risk telemetry.
            </div>
          ) : (
            <>
              {/* Summary Metric KPI Cards */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
                  gap: "1rem",
                  marginBottom: "1.25rem",
                }}
              >
                {/* Risk Level Card */}
                <div className="dash-card" style={{ padding: "1.1rem" }}>
                  <div style={{ color: "var(--dash-muted)", fontSize: "0.78rem", marginBottom: "0.4rem" }}>
                    Ramp Risk Status
                  </div>
                  <div style={{ display: "flex", alignItems: "baseline", gap: "0.5rem" }}>
                    <span
                      style={{
                        fontSize: "1.25rem",
                        fontWeight: 700,
                        textTransform: "uppercase",
                        color: getRiskColor(probData.summary.highest_risk_level),
                      }}
                    >
                      {probData.summary.highest_risk_level}
                    </span>
                    <span style={{ fontSize: "0.85rem", color: "var(--dash-muted)" }}>
                      Score: {probData.summary.ramp_risk_score}/100
                    </span>
                  </div>
                  <div style={{ fontSize: "0.76rem", color: "var(--dash-muted)", marginTop: "0.3rem" }}>
                    {probData.summary.critical_risk_event_count} Critical, {probData.summary.high_risk_event_count} High events
                  </div>
                </div>

                {/* Peak Ramp Rate Card */}
                <div className="dash-card" style={{ padding: "1.1rem" }}>
                  <div style={{ color: "var(--dash-muted)", fontSize: "0.78rem", marginBottom: "0.4rem" }}>
                    Peak Ramp Volatility
                  </div>
                  <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--dash-text)" }}>
                    {probData.summary.max_ramp_rate_kw_per_min.toFixed(2)}{" "}
                    <span style={{ fontSize: "0.85rem", fontWeight: 400, color: "var(--dash-muted)" }}>kW/min</span>
                  </div>
                  <div style={{ fontSize: "0.76rem", color: "var(--dash-muted)", marginTop: "0.3rem" }}>
                    Drop: -{probData.summary.max_ramp_down_kw_per_min.toFixed(1)} kW/m | Rise: +{probData.summary.max_ramp_up_kw_per_min.toFixed(1)} kW/m
                  </div>
                </div>

                {/* Uncertainty Band Card */}
                <div className="dash-card" style={{ padding: "1.1rem" }}>
                  <div style={{ color: "var(--dash-muted)", fontSize: "0.78rem", marginBottom: "0.4rem" }}>
                    Mean Uncertainty Envelope
                  </div>
                  <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--dash-sun)" }}>
                    {probData.summary.avg_uncertainty_band_kw.toFixed(1)}{" "}
                    <span style={{ fontSize: "0.85rem", fontWeight: 400, color: "var(--dash-muted)" }}>kW</span>
                  </div>
                  <div style={{ fontSize: "0.76rem", color: "var(--dash-muted)", marginTop: "0.3rem" }}>
                    Spread between P10 and P90 quantiles
                  </div>
                </div>

                {/* BESS Headroom Card */}
                <div className="dash-card" style={{ padding: "1.1rem" }}>
                  <div style={{ color: "var(--dash-muted)", fontSize: "0.78rem", marginBottom: "0.4rem" }}>
                    Recommended BESS Reserve
                  </div>
                  <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--dash-accent)" }}>
                    {probData.summary.recommended_bess_capacity_kw.toFixed(1)}{" "}
                    <span style={{ fontSize: "0.85rem", fontWeight: 400, color: "var(--dash-muted)" }}>kW</span>
                  </div>
                  <div style={{ fontSize: "0.76rem", color: "var(--dash-muted)", marginTop: "0.3rem" }}>
                    Headroom to buffer cloud-induced drops
                  </div>
                </div>
              </div>

              {/* Primary Action Advisory Banner */}
              <div
                style={{
                  background: `${getRiskColor(probData.summary.highest_risk_level)}15`,
                  borderLeft: `4px solid ${getRiskColor(probData.summary.highest_risk_level)}`,
                  padding: "0.85rem 1.15rem",
                  borderRadius: 6,
                  marginBottom: "1.5rem",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.75rem",
                }}
              >
                <span style={{ fontSize: "1.25rem" }}>
                  {probData.summary.highest_risk_level === "critical" ? "🚨" : probData.summary.highest_risk_level === "high" ? "⚠️" : "🛡️"}
                </span>
                <div>
                  <div style={{ fontWeight: 600, fontSize: "0.88rem", color: "var(--dash-text)" }}>
                    Grid Dispatch Advisory
                  </div>
                  <div style={{ fontSize: "0.82rem", color: "var(--dash-text)", opacity: 0.9 }}>
                    {probData.summary.primary_action_advisory}
                  </div>
                </div>
              </div>

              {/* Chart Card */}
              <div className="dash-card" style={{ marginBottom: "1.5rem" }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: "1rem",
                  }}
                >
                  <div>
                    <h2 style={{ fontSize: "1rem", fontWeight: 600, margin: 0 }}>
                      Uncertainty Ribbon & Ramp Trajectory
                    </h2>
                    <p style={{ fontSize: "0.78rem", color: "var(--dash-muted)", margin: "0.2rem 0 0" }}>
                      Hover over any interval to inspect P10/P50/P90 quantiles and cloud-passage volatility.
                    </p>
                  </div>
                  <span className="dash-badge dash-badge-muted">
                    Model: {probData.model_name}
                  </span>
                </div>

                <ProbabilisticBandChart
                  points={probData.points}
                  capacityKw={selectedPlant?.capacity_kw || 1000}
                />
              </div>

              {/* Cloud-Passage & Ramp Events Table */}
              <div className="dash-card">
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: "1rem",
                    flexWrap: "wrap",
                    gap: "0.5rem",
                  }}
                >
                  <div>
                    <h2 style={{ fontSize: "1rem", fontWeight: 600, margin: 0 }}>
                      Cloud-Passage & Ramp Interval Schedule
                    </h2>
                    <p style={{ fontSize: "0.78rem", color: "var(--dash-muted)", margin: "0.2rem 0 0" }}>
                      Time-series breakdown with dispatch recommendations for energy storage & spinning reserves.
                    </p>
                  </div>

                  <label
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.4rem",
                      fontSize: "0.82rem",
                      cursor: "pointer",
                      color: filterCriticalOnly ? "var(--dash-accent)" : "var(--dash-muted)",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={filterCriticalOnly}
                      onChange={(e) => setFilterCriticalOnly(e.target.checked)}
                    />
                    Show High & Critical Events Only ({probData.summary.critical_risk_event_count + probData.summary.high_risk_event_count})
                  </label>
                </div>

                <div className="dash-table-wrap">
                  <table className="dash-table">
                    <thead>
                      <tr>
                        <th>Interval Time</th>
                        <th>P50 Median (kW)</th>
                        <th>P10 Conservative (kW)</th>
                        <th>P90 Upper (kW)</th>
                        <th>Uncertainty (kW)</th>
                        <th>Ramp Rate (kW/min)</th>
                        <th>Risk Level</th>
                        <th>BESS Reserve (kW)</th>
                        <th>Operator Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {displayedPoints.length === 0 ? (
                        <tr>
                          <td colSpan={9} style={{ textAlign: "center", color: "var(--dash-muted)", padding: "2rem" }}>
                            No high or critical ramp risks detected in this horizon window.
                          </td>
                        </tr>
                      ) : (
                        displayedPoints.map((pt, idx) => (
                          <tr key={`pt-${idx}`}>
                            <td>{new Date(pt.forecast_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</td>
                            <td style={{ color: "var(--dash-accent)", fontWeight: 600 }}>
                              {pt.p50_kw.toFixed(1)}
                            </td>
                            <td style={{ color: "#5b9bd5" }}>{pt.p10_kw.toFixed(1)}</td>
                            <td style={{ color: "#f0a832" }}>{pt.p90_kw.toFixed(1)}</td>
                            <td>±{(pt.uncertainty_band_kw / 2).toFixed(1)}</td>
                            <td
                              style={{
                                color:
                                  pt.ramp_rate_kw_per_min < 0
                                    ? "#e85252"
                                    : pt.ramp_rate_kw_per_min > 0
                                    ? "#3dbd6e"
                                    : "var(--dash-muted)",
                                fontWeight: 500,
                              }}
                            >
                              {pt.ramp_rate_kw_per_min > 0 ? "+" : ""}
                              {pt.ramp_rate_kw_per_min.toFixed(2)}
                            </td>
                            <td>
                              <span
                                className="dash-badge"
                                style={{
                                  background: `${getRiskColor(pt.ramp_risk_level)}20`,
                                  color: getRiskColor(pt.ramp_risk_level),
                                  border: `1px solid ${getRiskColor(pt.ramp_risk_level)}`,
                                  textTransform: "uppercase",
                                  fontSize: "0.72rem",
                                  fontWeight: 700,
                                }}
                              >
                                {pt.ramp_risk_level}
                              </span>
                            </td>
                            <td style={{ color: "var(--dash-sun)", fontWeight: 600 }}>
                              {pt.bess_reserve_recommendation_kw.toFixed(1)}
                            </td>
                            <td style={{ fontSize: "0.8rem", color: "var(--dash-muted)" }}>
                              {pt.reserve_action}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </>
      )}

      {/* ── TAB 2: Point Forecast History ─────────────────────────────────────────── */}
      {activeTab === "history" && (
        <>
          {loadingFc ? (
            <div className="dash-loading">
              <div className="dash-spinner" />
              <div>Loading forecasts…</div>
            </div>
          ) : sortedForecasts.length === 0 ? (
            <div className="dash-card dash-empty">
              No point forecast records yet. Click &ldquo;Generate Point Forecast&rdquo; to create one.
            </div>
          ) : (
            <div className="dash-card">
              <div className="dash-table-wrap">
                <table className="dash-table">
                  <thead>
                    <tr>
                      <th>Forecast Time</th>
                      <th>Predicted (kW)</th>
                      <th>Actual (kW)</th>
                      <th>Physics (kW)</th>
                      <th>ML (kW)</th>
                      <th>Lower CI (P10)</th>
                      <th>Upper CI (P90)</th>
                      <th>Model</th>
                      <th>Generated At</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedForecasts.map((r) => (
                      <tr key={r.id}>
                        <td>{new Date(r.forecast_time).toLocaleString()}</td>
                        <td style={{ color: "var(--dash-accent)", fontWeight: 600 }}>
                          {r.predicted_power_kw.toFixed(2)}
                        </td>
                        <td>
                          {r.actual_power_kw != null ? (
                            <span style={{ color: "var(--dash-sun)" }}>
                              {r.actual_power_kw.toFixed(2)}
                            </span>
                          ) : (
                            <span style={{ color: "var(--dash-muted)" }}>—</span>
                          )}
                        </td>
                        <td>
                          {r.physics_power_kw != null
                            ? r.physics_power_kw.toFixed(2)
                            : <span style={{ color: "var(--dash-muted)" }}>—</span>}
                        </td>
                        <td>
                          {r.ml_power_kw != null
                            ? r.ml_power_kw.toFixed(2)
                            : <span style={{ color: "var(--dash-muted)" }}>—</span>}
                        </td>
                        <td style={{ color: "#5b9bd5" }}>
                          {r.confidence_lower != null ? r.confidence_lower.toFixed(2) : "—"}
                        </td>
                        <td style={{ color: "#f0a832" }}>
                          {r.confidence_upper != null ? r.confidence_upper.toFixed(2) : "—"}
                        </td>
                        <td>
                          <span className="dash-badge dash-badge-muted">{r.model_name}</span>
                        </td>
                        <td style={{ color: "var(--dash-muted)" }}>
                          {new Date(r.generated_at).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </>
  );
}
