"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { plantsApi, type PlantCreate } from "@/lib/api";

export default function NewPlantPage() {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState<PlantCreate>({
    name: "",
    location: "",
    latitude: 0,
    longitude: 0,
    timezone: "UTC",
    capacity_kw: 100,
    inverter_capacity_kw: 90,
    module_count: undefined,
  });

  function update(field: keyof PlantCreate, value: string | number | undefined) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    try {
      const payload: PlantCreate = {
        ...form,
        location: form.location || undefined,
        module_count: form.module_count || undefined,
      };
      const plant = await plantsApi.create(payload);
      router.push(`/dashboard/plants/${plant.id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create plant.");
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <div style={{ marginBottom: "1.75rem" }}>
        <h1 className="dash-section-title" style={{ marginBottom: "0.25rem" }}>
          Add New Plant
        </h1>
        <p style={{ color: "var(--dash-muted)", fontSize: "0.88rem" }}>
          Register a solar generation site with its physical parameters.
        </p>
      </div>

      {error && <div className="dash-error">⚠ {error}</div>}

      <div className="dash-card" style={{ maxWidth: 720 }}>
        <form onSubmit={onSubmit}>
          <div className="dash-form-grid">
            <div className="dash-field full">
              <label htmlFor="plant-name">Plant Name</label>
              <input
                id="plant-name"
                className="dash-input"
                type="text"
                required
                placeholder="e.g. Rajasthan North Array"
                value={form.name}
                onChange={(e) => update("name", e.target.value)}
              />
            </div>

            <div className="dash-field full">
              <label htmlFor="plant-location">Location (optional)</label>
              <input
                id="plant-location"
                className="dash-input"
                type="text"
                placeholder="e.g. Jodhpur, Rajasthan"
                value={form.location ?? ""}
                onChange={(e) => update("location", e.target.value)}
              />
            </div>

            <div className="dash-field">
              <label htmlFor="plant-lat">Latitude</label>
              <input
                id="plant-lat"
                className="dash-input"
                type="number"
                step="0.0001"
                min="-90"
                max="90"
                required
                value={form.latitude}
                onChange={(e) => update("latitude", parseFloat(e.target.value))}
              />
            </div>

            <div className="dash-field">
              <label htmlFor="plant-lon">Longitude</label>
              <input
                id="plant-lon"
                className="dash-input"
                type="number"
                step="0.0001"
                min="-180"
                max="180"
                required
                value={form.longitude}
                onChange={(e) => update("longitude", parseFloat(e.target.value))}
              />
            </div>

            <div className="dash-field">
              <label htmlFor="plant-tz">Timezone</label>
              <input
                id="plant-tz"
                className="dash-input"
                type="text"
                placeholder="UTC"
                value={form.timezone}
                onChange={(e) => update("timezone", e.target.value)}
              />
            </div>

            <div className="dash-field">
              <label htmlFor="plant-modules">Module Count (optional)</label>
              <input
                id="plant-modules"
                className="dash-input"
                type="number"
                min="1"
                placeholder="e.g. 400"
                value={form.module_count ?? ""}
                onChange={(e) =>
                  update(
                    "module_count",
                    e.target.value ? parseInt(e.target.value) : undefined
                  )
                }
              />
            </div>

            <div className="dash-field">
              <label htmlFor="plant-cap">DC Capacity (kW)</label>
              <input
                id="plant-cap"
                className="dash-input"
                type="number"
                min="0.1"
                step="0.1"
                required
                value={form.capacity_kw}
                onChange={(e) => update("capacity_kw", parseFloat(e.target.value))}
              />
            </div>

            <div className="dash-field">
              <label htmlFor="plant-inv">Inverter Capacity (kW)</label>
              <input
                id="plant-inv"
                className="dash-input"
                type="number"
                min="0.1"
                step="0.1"
                required
                value={form.inverter_capacity_kw}
                onChange={(e) =>
                  update("inverter_capacity_kw", parseFloat(e.target.value))
                }
              />
            </div>
          </div>

          <div
            style={{
              display: "flex",
              gap: "0.75rem",
              marginTop: "1.5rem",
              justifyContent: "flex-end",
            }}
          >
            <button
              type="button"
              className="dash-btn dash-btn-ghost"
              onClick={() => router.back()}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="dash-btn dash-btn-primary"
              disabled={pending}
            >
              {pending ? "Creating…" : "Create Plant"}
            </button>
          </div>
        </form>
      </div>
    </>
  );
}
