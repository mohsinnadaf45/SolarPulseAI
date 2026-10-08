import Image from "next/image";
import Link from "next/link";

export function Hero() {
  return (
    <section className="relative min-h-[100svh] overflow-hidden text-white">
      <Image
        src="https://images.unsplash.com/photo-1509391366360-2e959784a276?auto=format&fit=crop&w=2400&q=80"
        alt="Solar farm under open sky"
        fill
        priority
        className="object-cover object-center"
        sizes="100vw"
      />
      <div className="absolute inset-0 bg-[rgba(10,22,16,0.72)]" />

      <div className="relative z-10 mx-auto flex min-h-[100svh] max-w-6xl flex-col justify-end px-5 pb-16 pt-28 sm:px-8 sm:pb-20">
        <div className="max-w-3xl">
          <p className="animate-rise mb-4 flex items-center gap-2 font-[family-name:var(--font-display)] text-sm font-semibold uppercase tracking-[0.18em] text-[color:var(--sun)]">
            <span className="animate-dot inline-block h-2 w-2 rounded-[1px] bg-[color:var(--sun)]" />
            Operational prototype
          </p>
          <h1 className="animate-rise-delay-1 font-[family-name:var(--font-display)] text-5xl font-extrabold leading-[0.95] tracking-tight sm:text-6xl md:text-7xl">
            SolarPulse AI
          </h1>
          <div className="animate-line mt-5 h-px w-28 bg-[color:var(--sun)]" />
          <p className="animate-rise-delay-2 mt-6 max-w-xl text-lg leading-relaxed text-white/88 sm:text-xl">
            Hybrid yield forecasting that pairs solar physics with machine
            learning—so operators see deliverable AC power, not optimistic
            weather guesses.
          </p>
          <div className="animate-rise-delay-3 mt-9 flex flex-wrap gap-3">
            <Link href="/register" className="btn-primary">
              Create account
            </Link>
            <a href="#how-it-works" className="btn-ghost border-white/70 text-white">
              See how it works
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
