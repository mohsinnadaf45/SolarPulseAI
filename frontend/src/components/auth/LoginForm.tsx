"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

export function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setMessage(null);

    // Prototype UI — wire to FastAPI POST /auth/token when the API is available.
    await new Promise((resolve) => setTimeout(resolve, 450));
    setMessage(
      "Login is ready on the frontend. Connect NEXT_PUBLIC_API_URL to the FastAPI auth endpoint to complete sign-in.",
    );
    setPending(false);
  }

  return (
    <div>
      <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold tracking-tight">
        Log in
      </h1>
      <p className="mt-2 text-[color:var(--muted)]">
        Access the SolarPulse operator prototype with your account.
      </p>

      <form onSubmit={onSubmit} className="mt-8 space-y-4">
        <label className="block">
          <span className="mb-1.5 block text-sm font-semibold">Email</span>
          <input
            className="input-field"
            type="email"
            name="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>

        <label className="block">
          <span className="mb-1.5 block text-sm font-semibold">Password</span>
          <input
            className="input-field"
            type="password"
            name="password"
            autoComplete="current-password"
            required
            minLength={8}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>

        {message ? (
          <p
            role="status"
            className="border border-[color:var(--line)] bg-[color:var(--panel)] px-3 py-2 text-sm leading-relaxed text-[color:var(--muted)]"
          >
            {message}
          </p>
        ) : null}

        <button type="submit" className="btn-primary w-full" disabled={pending}>
          {pending ? "Signing in…" : "Log in"}
        </button>
      </form>

      <p className="mt-6 text-sm text-[color:var(--muted)]">
        No account yet?{" "}
        <Link
          href="/register"
          className="font-semibold text-[color:var(--field)] underline-offset-2 hover:underline"
        >
          Register
        </Link>
      </p>
    </div>
  );
}
