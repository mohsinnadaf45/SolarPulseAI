"use client";

import React from "react";
import type { DiagnosisResponse } from "@/lib/api";

interface DiagnosisModalProps {
  diagnosis: DiagnosisResponse;
  onClose: () => void;
  onResolveAlert?: (alertId: number) => void;
}

export default function DiagnosisModal({
  diagnosis,
  onClose,
  onResolveAlert,
}: DiagnosisModalProps) {
  const getUrgencyColor = (urgency: string) => {
    switch (urgency.toUpperCase()) {
      case "CRITICAL":
        return "#e85252";
      case "HIGH":
        return "#f0a832";
      case "MEDIUM":
        return "#e8c83a";
      default:
        return "#3dbd6e";
    }
  };

  const urgencyColor = getUrgencyColor(diagnosis.urgency_level);

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(0, 0, 0, 0.75)",
        backdropFilter: "blur(6px)",
        zIndex: 1000,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "1.5rem",
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "var(--dash-surface, #121f18)",
          border: "1px solid var(--dash-border, rgba(255,255,255,0.1))",
          borderRadius: 12,
          maxWidth: 780,
          width: "100%",
          maxHeight: "90vh",
          overflowY: "auto",
          boxShadow: "0 20px 50px rgba(0,0,0,0.6)",
          color: "var(--dash-text, #e8f0e8)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: "1.25rem 1.5rem",
            borderBottom: "1px solid var(--dash-border, rgba(255,255,255,0.08))",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "rgba(255,255,255,0.02)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <span style={{ fontSize: "1.5rem" }}>🔍</span>
            <div>
              <h2 style={{ fontSize: "1.15rem", fontWeight: 700, margin: 0 }}>
                AI Root-Cause Diagnosis
              </h2>
              <span style={{ fontSize: "0.78rem", color: "var(--dash-muted, #7a9e85)" }}>
                Plant #{diagnosis.plant_id} {diagnosis.plant_name ? `· ${diagnosis.plant_name}` : ""} ·{" "}
                {new Date(diagnosis.timestamp).toLocaleString()}
              </span>
            </div>
          </div>

          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              color: "var(--dash-muted)",
              fontSize: "1.25rem",
              cursor: "pointer",
              padding: "0.25rem 0.5rem",
            }}
          >
            ✕
          </button>
        </div>

        {/* Modal Body */}
        <div style={{ padding: "1.5rem" }}>
          {/* Top Badges & Metric Banner */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: "0.85rem",
              marginBottom: "1.25rem",
            }}
          >
            <div
              style={{
                background: "rgba(255,255,255,0.03)",
                padding: "0.85rem",
                borderRadius: 8,
                border: "1px solid var(--dash-border)",
              }}
            >
              <div style={{ fontSize: "0.74rem", color: "var(--dash-muted)" }}>Urgency Priority</div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginTop: "0.2rem" }}>
                <span
                  style={{
                    display: "inline-block",
                    width: 10,
                    height: 10,
                    borderRadius: "50%",
                    background: urgencyColor,
                  }}
                />
                <strong style={{ color: urgencyColor, fontSize: "0.95rem" }}>
                  {diagnosis.urgency_level}
                </strong>
              </div>
            </div>

            <div
              style={{
                background: "rgba(255,255,255,0.03)",
                padding: "0.85rem",
                borderRadius: 8,
                border: "1px solid var(--dash-border)",
              }}
            >
              <div style={{ fontSize: "0.74rem", color: "var(--dash-muted)" }}>AI Confidence Score</div>
              <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--dash-accent, #3dbd6e)", marginTop: "0.15rem" }}>
                {diagnosis.confidence_score.toFixed(0)}% Certainty
              </div>
            </div>

            <div
              style={{
                background: "rgba(255,255,255,0.03)",
                padding: "0.85rem",
                borderRadius: 8,
                border: "1px solid var(--dash-border)",
              }}
            >
              <div style={{ fontSize: "0.74rem", color: "var(--dash-muted)" }}>Daily Revenue Impact</div>
              <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--dash-sun, #f0a832)", marginTop: "0.15rem" }}>
                ${diagnosis.financial_impact_per_day.toFixed(2)}{" "}
                <span style={{ fontSize: "0.72rem", fontWeight: 400, color: "var(--dash-muted)" }}>/ day</span>
              </div>
            </div>

            <div
              style={{
                background: "rgba(255,255,255,0.03)",
                padding: "0.85rem",
                borderRadius: 8,
                border: "1px solid var(--dash-border)",
              }}
            >
              <div style={{ fontSize: "0.74rem", color: "var(--dash-muted)" }}>Power Deficit</div>
              <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--dash-text)", marginTop: "0.15rem" }}>
                {diagnosis.estimated_loss_kw.toFixed(1)}{" "}
                <span style={{ fontSize: "0.72rem", fontWeight: 400, color: "var(--dash-muted)" }}>kW loss</span>
              </div>
            </div>
          </div>

          {/* Primary Finding Card */}
          <div
            style={{
              background: "rgba(61, 189, 110, 0.05)",
              border: "1px solid rgba(61, 189, 110, 0.2)",
              borderRadius: 8,
              padding: "1rem 1.25rem",
              marginBottom: "1.25rem",
            }}
          >
            <div style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "var(--dash-accent)", fontWeight: 700 }}>
              Primary Diagnostic Root Cause
            </div>
            <h3 style={{ margin: "0.25rem 0 0.5rem", fontSize: "1.1rem", color: "var(--dash-text)" }}>
              {diagnosis.root_cause_title}
            </h3>
            <p style={{ margin: 0, fontSize: "0.86rem", color: "rgba(232, 240, 232, 0.88)", lineHeight: 1.5 }}>
              {diagnosis.root_cause_details}
            </p>
          </div>

          {/* Telemetry Evidence Pill Matrix */}
          {diagnosis.telemetry_evidence && (
            <div style={{ marginBottom: "1.25rem" }}>
              <div style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--dash-muted)", marginBottom: "0.5rem" }}>
                Observed Telemetry Evidence & Fault Signatures
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                {diagnosis.inverter_error_code && (
                  <span className="dash-badge" style={{ background: "rgba(232, 82, 82, 0.15)", color: "#e85252", border: "1px solid rgba(232, 82, 82, 0.3)" }}>
                    Error Code: {diagnosis.inverter_error_code}
                  </span>
                )}
                {diagnosis.telemetry_evidence.deficit_percentage != null && (
                  <span className="dash-badge" style={{ background: "rgba(240, 168, 50, 0.15)", color: "var(--dash-sun)", border: "1px solid rgba(240, 168, 50, 0.3)" }}>
                    {String(diagnosis.telemetry_evidence.deficit_percentage)}% Generation Deficit
                  </span>
                )}
                {diagnosis.telemetry_evidence.irradiance_w_m2 != null && (
                  <span className="dash-badge dash-badge-muted">
                    Irradiance: {String(diagnosis.telemetry_evidence.irradiance_w_m2)} W/m²
                  </span>
                )}
                {diagnosis.telemetry_evidence.temperature_c != null && (
                  <span className="dash-badge dash-badge-muted">
                    Ambient: {String(diagnosis.telemetry_evidence.temperature_c)}°C
                  </span>
                )}
                {diagnosis.telemetry_evidence.module_temp_c != null && (
                  <span className="dash-badge dash-badge-muted">
                    Module Temp: {String(diagnosis.telemetry_evidence.module_temp_c)}°C
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Safety Warning Banner */}
          {diagnosis.safety_warning && (
            <div
              style={{
                background: "rgba(232, 82, 82, 0.12)",
                borderLeft: "4px solid #e85252",
                padding: "0.85rem 1rem",
                borderRadius: 6,
                marginBottom: "1.25rem",
                fontSize: "0.84rem",
                color: "#ff8585",
                display: "flex",
                gap: "0.6rem",
                alignItems: "center",
              }}
            >
              <span style={{ fontSize: "1.25rem" }}>⚠️</span>
              <div>{diagnosis.safety_warning}</div>
            </div>
          )}

          {/* Step-by-Step Remediation Plan */}
          <div style={{ marginBottom: "1.25rem" }}>
            <h4 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "0.75rem", color: "var(--dash-text)" }}>
              Field Technician Remediation Procedure
            </h4>

            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              {diagnosis.technician_steps.map((s) => (
                <div
                  key={s.step_number}
                  style={{
                    background: "rgba(255, 255, 255, 0.02)",
                    border: "1px solid var(--dash-border)",
                    borderRadius: 8,
                    padding: "0.85rem 1rem",
                    display: "flex",
                    gap: "0.85rem",
                  }}
                >
                  <div
                    style={{
                      width: 28,
                      height: 28,
                      borderRadius: "50%",
                      background: "var(--dash-surface-2, #1a2e23)",
                      border: "1px solid var(--dash-accent)",
                      color: "var(--dash-accent)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontWeight: 700,
                      fontSize: "0.85rem",
                      flexShrink: 0,
                    }}
                  >
                    {s.step_number}
                  </div>

                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: "0.86rem", color: "var(--dash-text)", lineHeight: 1.45 }}>
                      {s.action}
                    </div>

                    {s.required_tools.length > 0 && (
                      <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginTop: "0.4rem", flexWrap: "wrap" }}>
                        <span style={{ fontSize: "0.72rem", color: "var(--dash-muted)" }}>Tools:</span>
                        {s.required_tools.map((tool, tIdx) => (
                          <span
                            key={tIdx}
                            style={{
                              fontSize: "0.7rem",
                              background: "rgba(255, 255, 255, 0.06)",
                              padding: "0.1rem 0.4rem",
                              borderRadius: 4,
                              color: "var(--dash-muted)",
                            }}
                          >
                            🔧 {tool}
                          </span>
                        ))}
                      </div>
                    )}

                    {s.safety_note && (
                      <div style={{ fontSize: "0.76rem", color: "var(--dash-warning, #e8a23a)", marginTop: "0.35rem" }}>
                        ⚡ {s.safety_note}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Preventative Advice */}
          {diagnosis.preventative_advice && (
            <div
              style={{
                background: "rgba(255, 255, 255, 0.02)",
                border: "1px dashed var(--dash-border)",
                borderRadius: 8,
                padding: "0.75rem 1rem",
                fontSize: "0.82rem",
                color: "var(--dash-muted)",
              }}
            >
              💡 <strong>Preventative Maintenance Recommendation:</strong> {diagnosis.preventative_advice}
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div
          style={{
            padding: "1rem 1.5rem",
            borderTop: "1px solid var(--dash-border)",
            display: "flex",
            justifyContent: "flex-end",
            gap: "0.75rem",
            background: "rgba(0,0,0,0.15)",
          }}
        >
          {diagnosis.alert_id && onResolveAlert && (
            <button
              className="dash-btn dash-btn-primary"
              onClick={() => {
                if (diagnosis.alert_id) {
                  onResolveAlert(diagnosis.alert_id);
                  onClose();
                }
              }}
            >
              ✓ Resolve Alert with Work Order Dispatched
            </button>
          )}

          <button className="dash-btn dash-btn-ghost" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
