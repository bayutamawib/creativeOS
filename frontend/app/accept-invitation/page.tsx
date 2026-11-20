"use client";
import { useState, type FormEvent } from "react";
import { mutate } from "@/lib/browser-api";
import { Button } from "@/components/ui/button";
import Link from "next/link";
export default function AcceptInvitation() {
  const [message, setMessage] = useState("");
  async function accept(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      await mutate("/auth/register", "POST", {
        token: window.location.hash.slice(1),
        full_name: data.get("full_name") || null,
        password: data.get("password") || null,
      });
      window.history.replaceState(null, "", "/accept-invitation");
      window.location.replace("/");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Invitation unavailable");
    }
  }
  return (
    <main className="mx-auto max-w-md space-y-5 px-6 py-16">
      <h1 className="text-3xl font-semibold">Accept your invitation</h1>
      <p>
        New members can set their name and password here. Existing members can{" "}
        <Link className="text-primary underline" href="/login" target="_blank">
          sign in
        </Link>{" "}
        and then accept.
      </p>
      <form method="post" onSubmit={accept} className="space-y-4">
        <label className="block">
          Name
          <input name="full_name" autoComplete="name" />
        </label>
        <label className="block">
          New password
          <input
            type="password"
            name="password"
            autoComplete="new-password"
            minLength={12}
          />
        </label>
        <Button>Accept invitation</Button>
      </form>
      <p role="status">{message}</p>
    </main>
  );
}
