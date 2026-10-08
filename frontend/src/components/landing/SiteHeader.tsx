import Link from "next/link";

export function SiteHeader() {
  return (
    <header className="absolute inset-x-0 top-0 z-20">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5 sm:px-8">
        <Link
          href="/"
          className="font-[family-name:var(--font-display)] text-lg font-bold tracking-tight text-white sm:text-xl"
        >
          SolarPulse AI
        </Link>
        <nav className="flex items-center gap-2 sm:gap-3">
          <a
            href="#features"
            className="hidden px-3 py-2 text-sm font-medium text-white/85 hover:text-white sm:inline"
          >
            Features
          </a>
          <a
            href="#how-it-works"
            className="hidden px-3 py-2 text-sm font-medium text-white/85 hover:text-white sm:inline"
          >
            How it works
          </a>
          <Link
            href="/login"
            className="px-3 py-2 text-sm font-medium text-white/90 hover:text-white"
          >
            Log in
          </Link>
          <Link href="/register" className="btn-primary text-sm">
            Register
          </Link>
        </nav>
      </div>
    </header>
  );
}
