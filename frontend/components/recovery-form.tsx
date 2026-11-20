"use client";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { mutate } from "@/lib/browser-api";

export function RecoveryForm({ reset }: { reset: boolean }) {
  const [message, setMessage] = useState("");
  const [complete, setComplete] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      if (reset) {
        await mutate("/auth/reset-password", "POST", {
          token: window.location.hash.slice(1),
          password: data.get("password"),
        });
        window.history.replaceState(null, "", "/reset-password");
        setMessage("Password updated. Sign in with your new password.");
      } else {
        await mutate("/auth/forgot-password", "POST", {
          email: data.get("email"),
        });
        setMessage(
          "If your account is active, reset instructions will be delivered.",
        );
      }
      setComplete(true);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Request failed");
    }
  }
  return (
    <main className="mx-auto max-w-md space-y-5 px-6 py-16">
      <h1 className="text-3xl font-semibold">
        {reset ? "Set a new password" : "Reset your password"}
      </h1>
      {!complete && (
        <form method="post" onSubmit={submit} className="space-y-4">
          {reset ? (
            <label className="block">
              New password
              <input
                name="password"
                type="password"
                autoComplete="new-password"
                minLength={12}
                maxLength={256}
                required
              />
            </label>
          ) : (
            <label className="block">
              Email address
              <input name="email" type="email" autoComplete="email" required />
            </label>
          )}
          <Button>{reset ? "Update password" : "Request reset"}</Button>
        </form>
      )}
      <p role="status">{message}</p>
      <Link className="text-primary underline" href="/login">
        Back to sign in
      </Link>
    </main>
  );
}
