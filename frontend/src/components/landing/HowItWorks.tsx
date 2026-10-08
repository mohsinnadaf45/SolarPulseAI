const steps = [
  {
    title: "Ingest weather and SCADA",
    body: "NWP feeds and plant telemetry land in TimescaleDB as the shared source of truth for every forecast run.",
  },
  {
    title: "Compute physics features",
    body: "pvlib derives solar position, plane-of-array irradiance, air mass, and cell temperature for the plant site.",
  },
  {
    title: "Run the ML forecast",
    body: "LightGBM combines physics features with meteorological inputs and historical power lags to estimate gross DC output.",
  },
  {
    title: "Apply operational constraints",
    body: "Inverter clipping and dynamic soiling convert the gross estimate into a deliverable AC forecast operators can trust.",
  },
  {
    title: "Surface shortfalls live",
    body: "The anomaly engine watches forecast versus SCADA. When the gap persists past a threshold, the dashboard gets an alert.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="bg-[color:var(--panel)]">
      <div className="mx-auto max-w-6xl px-5 py-20 sm:px-8 sm:py-24">
        <div className="max-w-2xl">
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[color:var(--muted)]">
            How it works
          </p>
          <h2 className="mt-3 font-[family-name:var(--font-display)] text-3xl font-bold tracking-tight sm:text-4xl">
            From raw signals to an actionable shortfall
          </h2>
          <p className="mt-4 text-lg leading-relaxed text-[color:var(--muted)]">
            A five-step pipeline keeps physics, machine learning, and plant
            constraints in the same loop—so the chart on screen matches what the
            site can actually export.
          </p>
        </div>

        <div className="mt-14 border-l border-[color:var(--line)] pl-6 sm:pl-8">
          {steps.map((step, index) => (
            <article key={step.title} className="relative pb-10 last:pb-0">
              <span className="absolute -left-[1.9rem] top-1 flex h-7 w-7 items-center justify-center border border-[color:var(--field)] bg-[color:var(--panel)] font-[family-name:var(--font-display)] text-xs font-bold text-[color:var(--field)] sm:-left-[2.15rem]">
                {index + 1}
              </span>
              <h3 className="font-[family-name:var(--font-display)] text-xl font-bold tracking-tight">
                {step.title}
              </h3>
              <p className="mt-2 max-w-2xl text-base leading-relaxed text-[color:var(--muted)]">
                {step.body}
              </p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
