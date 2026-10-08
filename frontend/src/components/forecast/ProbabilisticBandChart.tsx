"useclient";

import React, { useState, useRef } from "react";
import type { ProbabilisticForecastPoint } from "@/lib/api";

interface ProbabilisticBandChartProps {
  points: ProbabilisticForecastPoint[];
  capacityKw: number;
}

export default function ProbabilisticBandChart({
  points,
  capacityKw,
}: ProbabilisticBandChartProps) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [showP90, setShowP90] = useState(true);
  const [showP50, setShowP50] = useState(true);
  const [showP10, setShowP10] = useState(true);
  const [showRibbon, setShowRibbon] = useState(true);
  const svgRef = useRef<SVGSVGElement | null>(null);

  if (!points || points.length === 0) {
    return (
      <div className="dash-empty" style={{ padding: "3rem 1rem", textAlign: "center" }}>
        No probabilistic forecast data available for this selection.
      </div>
    );
  }

  const W = 920;
  const H = 300;
  const PAD = { top: 20, right: 28, bottom: 44, left: 60 };
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;

  const maxVal = Math.max(
    capacityKw,
    ...points.map((p) => Math.max(p.p90_kw, p.p50_kw, 1))
  );
  const minVal = 0;

  const xScale = (i: number) =>
    PAD.left + (i / Math.max(points.length - 1, 1)) * innerW;
  const yScale = (v: number) =>
    PAD.top + innerH - ((Math.max(0, v) - minVal) / Math.max(maxVal - minVal, 1)) * innerH;

  // Build SVG Paths
  const p90Coords = points.map((p, i) => ({ x: xScale(i), y: yScale(p.p90_kw) }));
  const p50Coords = points.map((p, i) => ({ x: xScale(i), y: yScale(p.p50_kw) }));
  const p10Coords = points.map((p, i) => ({ x: xScale(i), y: yScale(p.p10_kw) }));

  const pathFromCoords = (coords: { x: number; y: number }[]) =>
    coords.map((c, i) => `${i === 0 ? "M" : "L"}${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(" ");

  const p90Path = pathFromCoords(p90Coords);
  const p50Path = pathFromCoords(p50Coords);
  const p10Path = pathFromCoords(p10Coords);

  // Uncertainty Ribbon Area (P90 forward, P10 reverse)
  const ribbonPath = `${p90Path} ${p10Coords
    .slice()
    .reverse()
    .map((c) => `L${c.x.toFixed(1)},${c.y.toFixed(1)}`)
    .join(" ")} Z`;

  // Grid ticks
  const yTicks = 4;
  const yGrid = Array.from({ length: yTicks + 1 }, (_, i) => {
    const val = minVal + ((maxVal - minVal) * i) / yTicks;
    return { y: yScale(val), label: `${Math.round(val)} kW` };
  });

  const stepX = Math.max(1, Math.floor(points.length / 6));
  const xGrid = points
    .filter((_, i) => i % stepX === 0 || i === points.length - 1)
    .map((p) => {
      const idx = points.indexOf(p);
      const d = new Date(p.forecast_time);
      const label = `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
      return { x: xScale(idx), label };
    });

  const activePoint = hoverIndex != null ? points[hoverIndex] : null;

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const normX = (mouseX / rect.width) * W;

    // Find nearest point
    let nearestIdx = 0;
    let minDiff = Infinity;
    for (let i = 0; i < points.length; i++) {
      const diff = Math.abs(xScale(i) - normX);
      if (diff < minDiff) {
        minDiff = diff;
        nearestIdx = i;
      }
    }
    setHoverIndex(nearestIdx);
  };

  const getRiskBadgeColor = (level: string) => {
    switch (level) {
      case "critical":
        return "#e85252";
      case "high":
        return "#f0a832";
      case "medium":
        return "#3dbd6e";
      default:
        return "rgba(122, 158, 133, 0.7)";
    }
  };

  return (
    <div style={{ position: "relative" }}>
      {/* Interactive Legend & Filter Toggles */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "0.75rem",
          marginBottom: "0.85rem",
          padding: "0.5rem 0.75rem",
          background: "rgba(255, 255, 255, 0.02)",
          borderRadius: 8,
          border: "1px solid var(--dash-border)",
          fontSize: "0.82rem",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "1.25rem", flexWrap: "wrap" }}>
          <button
            type="button"
            onClick={() => setShowP90(!showP90)}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
              color: showP90 ? "#f0a832" : "var(--dash-muted)",
              opacity: showP90 ? 1 : 0.5,
              fontWeight: 500,
            }}
          >
            <span style={{ width: 14, height: 2, background: "#f0a832", borderTop: "2px dashed #f0a832" }} />
            P90 (Upper 90%)
          </button>

          <button
            type="button"
            onClick={() => setShowP50(!showP50)}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
              color: showP50 ? "#3dbd6e" : "var(--dash-muted)",
              opacity: showP50 ? 1 : 0.5,
              fontWeight: 600,
            }}
          >
            <span style={{ width: 14, height: 3, background: "#3dbd6e", borderRadius: 2 }} />
            P50 (Median Expected)
          </button>

          <button
            type="button"
            onClick={() => setShowP10(!showP10)}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
              color: showP10 ? "#5b9bd5" : "var(--dash-muted)",
              opacity: showP10 ? 1 : 0.5,
              fontWeight: 500,
            }}
          >
            <span style={{ width: 14, height: 2, background: "#5b9bd5", borderTop: "2px dotted #5b9bd5" }} />
            P10 (Lower 10%)
          </button>

          <button
            type="button"
            onClick={() => setShowRibbon(!showRibbon)}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
              color: showRibbon ? "var(--dash-text)" : "var(--dash-muted)",
              opacity: showRibbon ? 1 : 0.5,
            }}
          >
            <span
              style={{
                width: 14,
                height: 10,
                background: "linear-gradient(180deg, rgba(240,168,50,0.3), rgba(61,189,110,0.15))",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: 2,
              }}
            />
            Uncertainty Ribbon
          </button>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", color: "var(--dash-muted)" }}>
          <span style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#e85252" }} /> Critical Ramp
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#f0a832" }} /> High Ramp
          </span>
        </div>
      </div>

      {/* SVG Chart */}
      <div className="dash-chart-wrap" style={{ position: "relative" }}>
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          className="dash-chart-svg"
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHoverIndex(null)}
          style={{ width: "100%", height: "auto", display: "block", cursor: "crosshair" }}
        >
          <defs>
            <linearGradient id="probRibbonGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#f0a832" stopOpacity="0.32" />
              <stop offset="50%" stopColor="#3dbd6e" stopOpacity="0.22" />
              <stop offset="100%" stopColor="#5b9bd5" stopOpacity="0.12" />
            </linearGradient>
            <filter id="p50Glow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="0" stdDeviation="2" floodColor="#3dbd6e" floodOpacity="0.4" />
            </filter>
          </defs>

          {/* Grid lines and Y-axis */}
          {yGrid.map(({ y, label }) => (
            <g key={label}>
              <line
                x1={PAD.left}
                y1={y}
                x2={W - PAD.right}
                y2={y}
                stroke="rgba(255,255,255,0.06)"
                strokeDasharray="2 3"
              />
              <text
                x={PAD.left - 8}
                y={y + 4}
                textAnchor="end"
                fontSize="10"
                fill="rgba(122,158,133,0.8)"
              >
                {label}
              </text>
            </g>
          ))}

          {/* X-axis ticks */}
          {xGrid.map(({ x, label }) => (
            <text
              key={label + x}
              x={x}
              y={H - 14}
              textAnchor="middle"
              fontSize="10"
              fill="rgba(122,158,133,0.8)"
            >
              {label}
            </text>
          ))}

          {/* Uncertainty Ribbon */}
          {showRibbon && (
            <path
              d={ribbonPath}
              fill="url(#probRibbonGrad)"
              stroke="none"
              style={{ transition: "all 0.2s ease" }}
            />
          )}

          {/* P90 Upper Bound */}
          {showP90 && (
            <path
              d={p90Path}
              fill="none"
              stroke="#f0a832"
              strokeWidth="1.75"
              strokeDasharray="4 3"
              strokeLinecap="round"
            />
          )}

          {/* P10 Lower Bound */}
          {showP10 && (
            <path
              d={p10Path}
              fill="none"
              stroke="#5b9bd5"
              strokeWidth="1.75"
              strokeDasharray="3 3"
              strokeLinecap="round"
            />
          )}

          {/* P50 Median Forecast */}
          {showP50 && (
            <path
              d={p50Path}
              fill="none"
              stroke="#3dbd6e"
              strokeWidth="2.75"
              strokeLinecap="round"
              strokeLinejoin="round"
              filter="url(#p50Glow)"
            />
          )}

          {/* Ramp Risk Event Markers (High & Critical) */}
          {points.map((p, idx) => {
            if (p.ramp_risk_level !== "high" && p.ramp_risk_level !== "critical") {
              return null;
            }
            const cx = xScale(idx);
            const cy = yScale(p.p50_kw);
            const isCritical = p.ramp_risk_level === "critical";
            const color = isCritical ? "#e85252" : "#f0a832";

            return (
              <g key={`ramp-marker-${idx}`}>
                <circle
                  cx={cx}
                  cy={cy}
                  r={isCritical ? 7 : 5}
                  fill={color}
                  stroke="#121f18"
                  strokeWidth="2"
                />
                {isCritical && (
                  <circle
                    cx={cx}
                    cy={cy}
                    r="12"
                    fill="none"
                    stroke={color}
                    strokeWidth="1.5"
                    strokeOpacity="0.5"
                  />
                )}
              </g>
            );
          })}

          {/* Hover Crosshair and Focus Ring */}
          {hoverIndex != null && activePoint && (
            <g>
              <line
                x1={xScale(hoverIndex)}
                y1={PAD.top}
                x2={xScale(hoverIndex)}
                y2={PAD.top + innerH}
                stroke="rgba(255,255,255,0.4)"
                strokeDasharray="3 3"
                strokeWidth="1"
              />
              <circle
                cx={xScale(hoverIndex)}
                cy={yScale(activePoint.p50_kw)}
                r="6"
                fill="#3dbd6e"
                stroke="#fff"
                strokeWidth="2"
              />
              <circle
                cx={xScale(hoverIndex)}
                cy={yScale(activePoint.p90_kw)}
                r="4"
                fill="#f0a832"
                stroke="#fff"
                strokeWidth="1.5"
              />
              <circle
                cx={xScale(hoverIndex)}
                cy={yScale(activePoint.p10_kw)}
                r="4"
                fill="#5b9bd5"
                stroke="#fff"
                strokeWidth="1.5"
              />
            </g>
          )}
        </svg>

        {/* Hover Tooltip Overlay */}
        {hoverIndex != null && activePoint && (
          <div
            style={{
              position: "absolute",
              top: 12,
              right: 12,
              background: "rgba(18, 31, 24, 0.94)",
              backdropFilter: "blur(8px)",
              border: `1px solid ${getRiskBadgeColor(activePoint.ramp_risk_level)}`,
              boxShadow: "0 8px 24px rgba(0,0,0,0.5)",
              borderRadius: 8,
              padding: "0.85rem 1.1rem",
              fontSize: "0.82rem",
              minWidth: 260,
              pointerEvents: "none",
              zIndex: 10,
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "0.5rem",
                borderBottom: "1px solid var(--dash-border)",
                paddingBottom: "0.4rem",
              }}
            >
              <span style={{ fontWeight: 600, color: "var(--dash-text)" }}>
                {new Date(activePoint.forecast_time).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
              <span
                style={{
                  textTransform: "uppercase",
                  fontSize: "0.72rem",
                  fontWeight: 700,
                  padding: "0.15rem 0.5rem",
                  borderRadius: 4,
                  background: `${getRiskBadgeColor(activePoint.ramp_risk_level)}22`,
                  color: getRiskBadgeColor(activePoint.ramp_risk_level),
                  border: `1px solid ${getRiskBadgeColor(activePoint.ramp_risk_level)}`,
                }}
              >
                {activePoint.ramp_risk_level} Ramp Risk
              </span>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.4rem", marginBottom: "0.6rem" }}>
              <div>
                <span style={{ color: "var(--dash-muted)", fontSize: "0.75rem" }}>P50 Expected:</span>{" "}
                <strong style={{ color: "#3dbd6e" }}>{activePoint.p50_kw.toFixed(1)} kW</strong>
              </div>
              <div>
                <span style={{ color: "var(--dash-muted)", fontSize: "0.75rem" }}>P90 Optimistic:</span>{" "}
                <strong style={{ color: "#f0a832" }}>{activePoint.p90_kw.toFixed(1)} kW</strong>
              </div>
              <div>
                <span style={{ color: "var(--dash-muted)", fontSize: "0.75rem" }}>P10 Conservative:</span>{" "}
                <strong style={{ color: "#5b9bd5" }}>{activePoint.p10_kw.toFixed(1)} kW</strong>
              </div>
              <div>
                <span style={{ color: "var(--dash-muted)", fontSize: "0.75rem" }}>Uncertainty Band:</span>{" "}
                <strong style={{ color: "var(--dash-text)" }}>{activePoint.uncertainty_band_kw.toFixed(1)} kW</strong>
              </div>
            </div>

            <div style={{ borderTop: "1px solid var(--dash-border)", paddingTop: "0.4rem", fontSize: "0.78rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.2rem" }}>
                <span style={{ color: "var(--dash-muted)" }}>Ramp Rate:</span>
                <span
                  style={{
                    color:
                      activePoint.ramp_rate_kw_per_min < 0
                        ? "#e85252"
                        : activePoint.ramp_rate_kw_per_min > 0
                        ? "#3dbd6e"
                        : "var(--dash-muted)",
                    fontWeight: 600,
                  }}
                >
                  {activePoint.ramp_rate_kw_per_min > 0 ? "+" : ""}
                  {activePoint.ramp_rate_kw_per_min.toFixed(2)} kW/min (
                  {activePoint.ramp_direction.toUpperCase()})
                </span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.25rem" }}>
                <span style={{ color: "var(--dash-muted)" }}>BESS Reserve Buffer:</span>
                <span style={{ color: "var(--dash-sun)", fontWeight: 600 }}>
                  {activePoint.bess_reserve_recommendation_kw.toFixed(1)} kW
                </span>
              </div>
              <div style={{ color: "var(--dash-muted)", fontStyle: "italic", marginTop: "0.35rem", fontSize: "0.74rem" }}>
                💡 {activePoint.reserve_action}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
