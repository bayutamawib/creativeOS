"use client";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { mutate } from "@/lib/browser-api";
export function Inquiry() {
  const [sent, setSent] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const data = Object.fromEntries(new FormData(e.currentTarget));
    try {
      await mutate("/public/inquiries", "POST", data);
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed");
    } finally {
      setBusy(false);
    }
  }
  if (sent)
    return (
      <div role="status">
        <h2>Inquiry received</h2>
        <p>
          The agency will review your request and follow up with your contact.
        </p>
      </div>
    );
  return (
    <form method="post" onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
      <label>
        Company name
        <input
          name="company_name"
          autoComplete="organization"
          required
          maxLength={200}
        />
      </label>
      <label>
        Contact name
        <input
          name="contact_name"
          autoComplete="name"
          required
          maxLength={150}
        />
      </label>
      <label>
        Email address
        <input
          name="email"
          type="email"
          autoComplete="email"
          required
          maxLength={255}
        />
      </label>
      <label>
        Phone (optional)
        <input name="phone" type="tel" maxLength={30} />
      </label>
      <label>
        Industry (optional)
        <input name="industry" maxLength={100} />
      </label>
      <label>
        Service of interest
        <input name="service_interest" maxLength={500} />
      </label>
      <label className="sm:col-span-2">
        Tell us about your project
        <textarea name="inquiry_message" maxLength={5000} rows={4} />
      </label>
      <label hidden>
        Leave empty
        <input name="website_confirmation" tabIndex={-1} autoComplete="off" />
      </label>
      <div>
        <Button disabled={busy}>Submit inquiry</Button>
      </div>
      <p role="alert">{error}</p>
    </form>
  );
}
