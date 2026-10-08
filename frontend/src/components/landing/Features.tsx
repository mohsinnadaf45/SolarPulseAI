const features = [
  {
    title: "Hybrid yield forecasting",
    body: "pvlib physics features feed a LightGBM model for sub-hourly to hourly AC generation forecasts grounded in real plant geometry.",
  },
  {
    title: "Inverter clipping",
    body: "Hard-caps DC output at the AC export limit of the inverter or interconnection agreement, so forecasts match what the grid can take.",
  },
  {
    title: "Dynamic soiling estimation",
    body: "Models particulate buildup from time-since-rain and cleaning logs. Rain events trigger automatic recovery in the loss curve.",
  },
  {
    title: "Anomaly detection",
    body: "Compares deliverable forecast against live SCADA. Persistent shortfalls raise operational alerts before they become revenue loss.",
  },
];

export function Features() {
  return (
    <section id="features" className="site-grid border-y border-[color:var(--line)]">
      <div className="mx-auto max-w-6xl px-5 py-20 sm:px-8 sm:py-24">
        <div className="max-w-2xl">
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[color:var(--muted)]">
            Prototype capabilities
          </p>
          <h2 className="mt-3 font-[family-name:var(--font-display)] text-3xl font-bold tracking-tight text-[color:var(--ink)] sm:text-4xl">
            Built for plant operators who need realistic numbers
          </h2>
          <p className="mt-4 text-lg leading-relaxed text-[color:var(--muted)]">
            The MVP focuses on four operational layers—physics, ML, constraints,
            and live shortfall detection—without burying the signal in dashboard
            noise.
          </p>
        </div>

        <ol className="mt-14 divide-y divide-[color:var(--line)] border-y border-[color:var(--line)]">
          {features.map((feature, index) => (
            <li
              key={feature.title}
              className="grid gap-4 py-8 sm:grid-cols-[5rem_1fr] sm:gap-10"
            >
              <span className="font-[family-name:var(--font-display)] text-2xl font-bold text-[color:var(--field)]">
                {String(index + 1).padStart(2, "0")}
              </span>
              <div>
                <h3 className="font-[family-name:var(--font-display)] text-xl font-bold tracking-tight">
                  {feature.title}
                </h3>
                <p className="mt-2 max-w-2xl text-base leading-relaxed text-[color:var(--muted)]">
                  {feature.body}
                </p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
