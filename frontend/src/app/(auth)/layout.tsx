import Link from "next/link";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="site-grid min-h-[100svh]">
      <div className="mx-auto flex min-h-[100svh] w-full max-w-md flex-col px-5 py-8 sm:px-6">
        <Link
          href="/"
          className="font-[family-name:var(--font-display)] text-lg font-bold tracking-tight text-[color:var(--field)]"
        >
          SolarPulse AI
        </Link>
        <div className="flex flex-1 flex-col justify-center py-10">{children}</div>
      </div>
    </div>
  );
}
