"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { isLoggedIn, logout } from "@/lib/api";

export function SiteHeader() {
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    setLoggedIn(isLoggedIn());
  }, []);

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
          {loggedIn ? (
            <>
              <Link href="/dashboard" className="btn-primary text-sm">
                Dashboard
              </Link>
              <button
                onClick={logout}
                className="px-3 py-2 text-sm font-medium text-white/90 hover:text-white bg-transparent border-0 cursor-pointer"
              >
                Sign out
              </button>
            </>
          ) : (
            <>
              <Link
                href="/login"
                className="px-3 py-2 text-sm font-medium text-white/90 hover:text-white"
              >
                Log in
              </Link>
              <Link href="/register" className="btn-primary text-sm">
                Register
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
