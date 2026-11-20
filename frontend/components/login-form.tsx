"use client";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { mutate } from "@/lib/browser-api";
export function LoginForm() {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      await mutate("/auth/login", "POST", {
        email: form.get("email"),
        password: form.get("password"),
      });
      window.location.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed");
      setBusy(false);
    }
  }
  return (
    <form
      method="post"
      onSubmit={submit}
      className="space-y-5 rounded-2xl border border-border bg-white p-7 shadow-sm sm:p-9"
    >
      <label className="block text-sm font-medium">
        Email address
        <input
          type="email"
          autoComplete="username"
          name="email"
          required
          className="mt-2"
        />
      </label>
      <label className="block text-sm font-medium">
        Password
        <input
          type="password"
          autoComplete="current-password"
          name="password"
          required
          className="mt-2"
        />
      </label>
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}
      <Button size="lg" className="w-full" disabled={busy}>
        {busy ? "Signing in…" : "Sign in"}
      </Button>
      <Link
        className="block text-center text-sm text-primary"
        href="/forgot-password"
      >
        Forgot password?
      </Link>
    </form>
  );
}
