"use client";

import Link from "next/link";
import { useEffect, useState, useCallback } from "react";
import { plantsApi, type Plant } from "@/lib/api";

export default function PlantsPage() {
  const [plants, setPlants] = useState<Plant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await plantsApi.list();
      setPlants(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load plants.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "1.75rem",
        }}
      >
        <div>
          <h1 className="dash-section-title" style={{ marginBottom: "0.25rem" }}>
            Plants
          </h1>
          <p style={{ color: "var(--dash-muted)", fontSize: "0.88rem" }}>
            Manage your registered solar generation sites.
          </p>
        </div>
        <Link href="/dashboard/plants/new" className="dash-btn dash-btn-primary">
          + Add Plant
        </Link>
      </div>

      {error && <div className="dash-error">⚠ {error}</div>}

      {loading ? (
        <div className="dash-loading">
          <div className="dash-spinner" />
          <div>Loading plants…</div>
        </div>
      ) : plants.length === 0 ? (
        <div className="dash-card dash-empty">
          <p>No plants registered yet.</p>
          <Link
            href="/dashboard/plants/new"
            className="dash-btn dash-btn-primary"
            style={{ marginTop: "1rem" }}
          >
            Register your first plant →
          </Link>
        </div>
      ) : (
        <div className="dash-card">
          <div className="dash-table-wrap">
            <table className="dash-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Location</th>
                  <th>Capacity</th>
                  <th>Inverter</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {plants.map((plant) => (
                  <tr key={plant.id}>
                    <td style={{ fontWeight: 600, color: "var(--dash-text)" }}>
                      {plant.name}
                    </td>
                    <td style={{ color: "var(--dash-muted)" }}>
                      {plant.location ??
                        `${plant.latitude.toFixed(3)}, ${plant.longitude.toFixed(3)}`}
                    </td>
                    <td>{plant.capacity_kw} kW</td>
                    <td>{plant.inverter_capacity_kw} kW</td>
                    <td>
                      {plant.is_active ? (
                        <span className="dash-badge dash-badge-green">Active</span>
                      ) : (
                        <span className="dash-badge dash-badge-muted">Inactive</span>
                      )}
                    </td>
                    <td style={{ color: "var(--dash-muted)" }}>
                      {new Date(plant.created_at).toLocaleDateString()}
                    </td>
                    <td>
                      <Link
                        href={`/dashboard/plants/${plant.id}`}
                        className="dash-btn dash-btn-ghost"
                        style={{ fontSize: "0.78rem", padding: "0.3rem 0.7rem" }}
                      >
                        View →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
