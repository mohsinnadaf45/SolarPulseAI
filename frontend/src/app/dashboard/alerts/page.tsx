"use client";

import { useCallback, useEffect, useState } from "react";
import {
  alertsApi,
  diagnosisApi,
  plantsApi,
  type Alert,
  type Plant,
  type DiagnosisResponse,
  type RootCauseTaxonomyItem,
} from "@/lib/api";
import DiagnosisModal from "@/components/diagnosis/DiagnosisModal";

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [plants, setPlants] = useState<Plant[]>([]);
  const [taxonomy, setTaxonomy] = useState<RootCauseTaxonomyItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "open" | "resolved">("open");
  const [viewTab, setViewTab] = useState<"alerts" | "sandbox">("alerts");

  // Diagnosis Modal state
  const [activeDiagnosis, setActiveDiagnosis] = useState<DiagnosisResponse | null>(null);
  const [diagnosingId, setDiagnosingId] = useState<number | null>(null);

  // Diagnostic Sandbox state
  const [customPlantId, setCustomPlantId] = useState<number | null>(null);
  const [selectedErrorCode, setSelectedErrorCode] = useState<string>("F056");
  const [customExpectedKw, setCustomExpectedKw] = useState<string>("42000");
  const [customActualKw, setCustomActualKw] = useState<string>("28000");
  const [customIrradiance, setCustomIrradiance] = useState<string>("850");
  const [customTemp, setCustomTemp] = useState<string>("38");
  const [runningSandbox, setRunningSandbox] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [alertData, plantData, taxData] = await Promise.all([
        alertsApi.list(undefined, 200),
        plantsApi.list(),
        diagnosisApi.getTaxonomy().catch(() => []),
      ]);
      setAlerts(alertData);
      setPlants(plantData);
      setTaxonomy(taxData);
      if (plantData.length > 0) setCustomPlantId(plantData[0].id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load alerts.");
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

  const handleDiagnoseAlert = async (alertId: number) => {
    setDiagnosingId(alertId);
    setError(null);
    try {
      const diag = await diagnosisApi.diagnoseAlert(alertId);
      setActiveDiagnosis(diag);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Diagnosis calculation failed.");
    } finally {
      setDiagnosingId(null);
    }
  };

  const handleRunSandbox = async () => {
    if (!customPlantId) return;
    setRunningSandbox(true);
    setError(null);
    try {
      const diag = await diagnosisApi.diagnose({
        plant_id: customPlantId,
        inverter_error_code: selectedErrorCode,
        expected_power_kw: parseFloat(customExpectedKw) || 1000,
        actual_power_kw: parseFloat(customActualKw) || 600,
        irradiance_w_m2: parseFloat(customIrradiance) || 800,
        temperature_c: parseFloat(customTemp) || 30,
      });
      setActiveDiagnosis(diag);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Diagnostic execution failed.");
    } finally {
      setRunningSandbox(false);
    }
  };

  const filtered = alerts.filter((a) => {
    if (filter === "open") return !a.is_resolved;
    if (filter === "resolved") return a.is_resolved;
    return true;
  });

  const counts = {
    all: alerts.length,
    open: alerts.filter((a) => !a.is_resolved).length,
    resolved: alerts.filter((a) => a.is_resolved).length,
  };

  return (
    <>
      <div style={{ marginBottom: "1.5rem" }}>
        <h1 className="dash-section-title" style={{ marginBottom: "0.25rem" }}>
          Alerts & AI Root-Cause Diagnostics
        </h1>
        <p style={{ color: "var(--dash-muted)", fontSize: "0.88rem" }}>
          Automated fault classification, multi-vendor inverter error code diagnosis, and field technician dispatch work orders.
        </p>
      </div>

      {error && <div className="dash-error" style={{ marginBottom: "1.25rem" }}>⚠ {error}</div>}

      {/* Main Mode Tabs */}
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
          onClick={() => setViewTab("alerts")}
          style={{
            background: "none",
            border: "none",
            padding: "0.6rem 1.25rem",
            cursor: "pointer",
            fontWeight: 600,
            fontSize: "0.9rem",
            color: viewTab === "alerts" ? "var(--dash-accent)" : "var(--dash-muted)",
            borderBottom: viewTab === "alerts" ? "2px solid var(--dash-accent)" : "2px solid transparent",
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
          }}
        >
          <span>🔔</span> Anomaly Alerts Log ({counts.open} Open)
        </button>

        <button
          type="button"
          onClick={() => setViewTab("sandbox")}
          style={{
            background: "none",
            border: "none",
            padding: "0.6rem 1.25rem",
            cursor: "pointer",
            fontWeight: 600,
            fontSize: "0.9rem",
            color: viewTab === "sandbox" ? "var(--dash-accent)" : "var(--dash-muted)",
            borderBottom: viewTab === "sandbox" ? "2px solid var(--dash-accent)" : "2px solid transparent",
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
          }}
        >
          <span>⚡</span> Inverter Error Code Diagnostic Sandbox
        </button>
      </div>

      {/* ── TAB 1: Alerts Log ──────────────────────────────────────────────────────── */}
      {viewTab === "alerts" && (
        <>
          {/* Filter pills */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "1.25rem",
              flexWrap: "wrap",
              gap: "0.75rem",
            }}
          >
            <div style={{ display: "flex", gap: "0.5rem" }}>
              {(["open", "all", "resolved"] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`dash-btn ${filter === f ? "dash-btn-primary" : "dash-btn-ghost"}`}
                  style={{ fontSize: "0.82rem" }}
                >
                  {f.charAt(0).toUpperCase() + f.slice(1)}{" "}
                  <span
                    style={{
                      background: "rgba(255,255,255,0.12)",
                      borderRadius: 3,
                      padding: "0 0.35rem",
                      fontSize: "0.72rem",
                    }}
                  >
                    {counts[f]}
                  </span>
                </button>
              ))}
            </div>

            <div style={{ fontSize: "0.8rem", color: "var(--dash-muted)" }}>
              Tip: Click <strong>⚡ AI Diagnose</strong> to analyze inverter error codes and generate technician work orders.
            </div>
          </div>

          {loading ? (
            <div className="dash-loading">
              <div className="dash-spinner" />
              <div>Loading alerts…</div>
            </div>
          ) : filtered.length === 0 ? (
            <div className="dash-card dash-empty">
              {filter === "open" ? "No open alerts — all clear 🎉" : "No alerts in this category."}
            </div>
          ) : (
            <div className="dash-card">
              <div className="dash-alert-list">
                {filtered.map((a) => {
                  const severity = a.severity as "CRITICAL" | "WARNING" | "INFO";
                  const isDiagnosing = diagnosingId === a.id;

                  return (
                    <div key={a.id} className={`dash-alert-row ${severity}`}>
                      <span className={`dash-alert-badge ${severity}`}>{severity}</span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div className="dash-alert-msg" style={{ fontWeight: 600 }}>
                          {a.message}
                        </div>
                        <div
                          style={{
                            fontSize: "0.74rem",
                            color: "var(--dash-muted)",
                            marginTop: "0.25rem",
                            display: "flex",
                            gap: "0.6rem",
                            flexWrap: "wrap",
                          }}
                        >
                          <span>Plant #{a.plant_id}</span>
                          <span>· Type: {a.alert_type}</span>
                          {a.deviation_percent != null && (
                            <span>· {a.deviation_percent.toFixed(1)}% power shortfall</span>
                          )}
                          {a.expected_power_kw != null && a.actual_power_kw != null && (
                            <span>· {a.actual_power_kw.toFixed(0)} kW / {a.expected_power_kw.toFixed(0)} kW</span>
                          )}
                        </div>
                      </div>

                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexShrink: 0 }}>
                        <span className="dash-alert-time" style={{ marginRight: "0.5rem" }}>
                          {new Date(a.timestamp).toLocaleString()}
                        </span>

                        <button
                          className="dash-btn dash-btn-ghost"
                          style={{
                            fontSize: "0.76rem",
                            padding: "0.3rem 0.65rem",
                            border: "1px solid rgba(61, 189, 110, 0.4)",
                            color: "var(--dash-accent)",
                          }}
                          onClick={() => handleDiagnoseAlert(a.id)}
                          disabled={isDiagnosing}
                        >
                          {isDiagnosing ? "Diagnosing…" : "⚡ AI Diagnose"}
                        </button>

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
                              fontSize: "0.72rem",
                              color: "var(--dash-accent)",
                              fontWeight: 600,
                            }}
                          >
                            ✓ Resolved
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}

      {/* ── TAB 2: Diagnostic Sandbox ────────────────────────────────────────────── */}
      {viewTab === "sandbox" && (
        <div className="dash-card">
          <div style={{ marginBottom: "1.25rem" }}>
            <h2 style={{ fontSize: "1.05rem", fontWeight: 700, margin: 0 }}>
              On-Demand Inverter Fault & Telemetry Diagnostic Tool
            </h2>
            <p style={{ fontSize: "0.82rem", color: "var(--dash-muted)", margin: "0.25rem 0 0" }}>
              Input any standard inverter fault code or observed telemetry shortfall to compute AI root-cause analysis and generate actionable field technician procedures.
            </p>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              gap: "1rem",
              marginBottom: "1.25rem",
            }}
          >
            <div>
              <label style={{ fontSize: "0.78rem", color: "var(--dash-muted)", display: "block", marginBottom: "0.3rem" }}>
                Target Solar Plant:
              </label>
              <select
                className="dash-input"
                style={{ width: "100%", padding: "0.5rem" }}
                value={customPlantId ?? ""}
                onChange={(e) => setCustomPlantId(parseInt(e.target.value, 10))}
              >
                {plants.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.capacity_kw} kW)
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label style={{ fontSize: "0.78rem", color: "var(--dash-muted)", display: "block", marginBottom: "0.3rem" }}>
                Inverter Error Code:
              </label>
              <input
                type="text"
                className="dash-input"
                style={{ width: "100%", padding: "0.5rem" }}
                value={selectedErrorCode}
                onChange={(e) => setSelectedErrorCode(e.target.value)}
                placeholder="e.g. F056, F034, AFCI, F012"
              />
            </div>

            <div>
              <label style={{ fontSize: "0.78rem", color: "var(--dash-muted)", display: "block", marginBottom: "0.3rem" }}>
                Expected Power (kW):
              </label>
              <input
                type="number"
                className="dash-input"
                style={{ width: "100%", padding: "0.5rem" }}
                value={customExpectedKw}
                onChange={(e) => setCustomExpectedKw(e.target.value)}
              />
            </div>

            <div>
              <label style={{ fontSize: "0.78rem", color: "var(--dash-muted)", display: "block", marginBottom: "0.3rem" }}>
                Actual Power (kW):
              </label>
              <input
                type="number"
                className="dash-input"
                style={{ width: "100%", padding: "0.5rem" }}
                value={customActualKw}
                onChange={(e) => setCustomActualKw(e.target.value)}
              />
            </div>

            <div>
              <label style={{ fontSize: "0.78rem", color: "var(--dash-muted)", display: "block", marginBottom: "0.3rem" }}>
                Irradiance (W/m²):
              </label>
              <input
                type="number"
                className="dash-input"
                style={{ width: "100%", padding: "0.5rem" }}
                value={customIrradiance}
                onChange={(e) => setCustomIrradiance(e.target.value)}
              />
            </div>

            <div>
              <label style={{ fontSize: "0.78rem", color: "var(--dash-muted)", display: "block", marginBottom: "0.3rem" }}>
                Ambient Temperature (°C):
              </label>
              <input
                type="number"
                className="dash-input"
                style={{ width: "100%", padding: "0.5rem" }}
                value={customTemp}
                onChange={(e) => setCustomTemp(e.target.value)}
              />
            </div>
          </div>

          {/* Quick preset chips */}
          <div style={{ marginBottom: "1.5rem" }}>
            <div style={{ fontSize: "0.75rem", color: "var(--dash-muted)", marginBottom: "0.4rem" }}>
              Quick Error Code Presets (Click to load):
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
              {[
                { code: "F056", label: "F056: Inverter Overtemp / Fan Trip" },
                { code: "F034", label: "F034: DC Ground Fault (Low Riso)" },
                { code: "F012", label: "F012: DC String Open-Circuit" },
                { code: "F063", label: "F063: DC Arc Fault (AFCI)" },
                { code: "F021", label: "F021: Grid Overvoltage Curtailment" },
                { code: "F077", label: "F077: MPPT Tracker Stalled" },
                { code: "SOILING", label: "SOILING: Particulate Dust Deficit" },
                { code: "CLIPPING", label: "CLIPPING: Inverter AC Power Saturation" },
              ].map((preset) => (
                <button
                  key={preset.code}
                  type="button"
                  onClick={() => setSelectedErrorCode(preset.code)}
                  style={{
                    background: selectedErrorCode === preset.code ? "rgba(61, 189, 110, 0.2)" : "rgba(255, 255, 255, 0.04)",
                    border: `1px solid ${selectedErrorCode === preset.code ? "var(--dash-accent)" : "var(--dash-border)"}`,
                    color: selectedErrorCode === preset.code ? "var(--dash-accent)" : "var(--dash-text)",
                    padding: "0.25rem 0.6rem",
                    borderRadius: 4,
                    fontSize: "0.74rem",
                    cursor: "pointer",
                  }}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>

          <button
            className="dash-btn dash-btn-primary"
            onClick={handleRunSandbox}
            disabled={runningSandbox || !customPlantId}
            style={{ padding: "0.6rem 1.5rem", fontSize: "0.9rem" }}
          >
            {runningSandbox ? "Executing Diagnostic Inference…" : "🔍 Run AI Root-Cause Diagnosis"}
          </button>

          {taxonomy.length > 0 && (
            <div style={{ marginTop: "2rem", borderTop: "1px solid var(--dash-border)", paddingTop: "1.25rem" }}>
              <h3 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "0.75rem", color: "var(--dash-text)" }}>
                Diagnostic Fault Taxonomy & Supported Code Signatures ({taxonomy.length} Categories)
              </h3>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "0.75rem" }}>
                {taxonomy.map((t) => (
                  <div
                    key={t.category}
                    style={{
                      background: "rgba(255,255,255,0.02)",
                      border: "1px solid var(--dash-border)",
                      borderRadius: 8,
                      padding: "0.75rem 1rem",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.3rem" }}>
                      <strong style={{ fontSize: "0.85rem", color: "var(--dash-text)" }}>{t.title}</strong>
                      <span className="dash-badge dash-badge-muted" style={{ fontSize: "0.68rem" }}>{t.typical_urgency}</span>
                    </div>
                    <p style={{ fontSize: "0.78rem", color: "var(--dash-muted)", margin: "0 0 0.4rem", lineHeight: 1.4 }}>
                      {t.description}
                    </p>
                    <div style={{ display: "flex", gap: "0.3rem", flexWrap: "wrap", alignItems: "center" }}>
                      <span style={{ fontSize: "0.7rem", color: "var(--dash-muted)" }}>Codes:</span>
                      {t.common_error_codes.map((c) => (
                        <button
                          key={c}
                          type="button"
                          onClick={() => setSelectedErrorCode(c)}
                          style={{
                            background: "rgba(61, 189, 110, 0.1)",
                            color: "var(--dash-accent)",
                            border: "1px solid rgba(61, 189, 110, 0.2)",
                            borderRadius: 4,
                            padding: "0.1rem 0.35rem",
                            fontSize: "0.68rem",
                            cursor: "pointer",
                          }}
                        >
                          {c}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Diagnosis Inspection Modal */}
      {activeDiagnosis && (
        <DiagnosisModal
          diagnosis={activeDiagnosis}
          onClose={() => setActiveDiagnosis(null)}
          onResolveAlert={handleResolve}
        />
      )}
    </>
  );
}
