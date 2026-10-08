import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="border-t border-[color:var(--line)] bg-[color:var(--field)] text-[#e8efe8]">
      <div className="mx-auto flex max-w-6xl flex-col gap-8 px-5 py-12 sm:flex-row sm:items-end sm:justify-between sm:px-8">
        <div>
          <p className="font-[family-name:var(--font-display)] text-2xl font-bold tracking-tight">
            SolarPulse AI
          </p>
          <p className="mt-2 max-w-md text-sm leading-relaxed text-[#c5d2c5]">
            Hybrid solar yield forecasting and plant performance monitoring
            prototype. Register to explore the operator dashboard as the backend
            comes online.
          </p>
        </div>
        <div className="flex gap-4 text-sm font-semibold">
          <Link href="/login" className="hover:underline">
            Log in
          </Link>
          <Link href="/register" className="hover:underline">
            Register
          </Link>
          <a href="#features" className="hover:underline">
            Features
          </a>
        </div>
      </div>
    </footer>
  );
}
