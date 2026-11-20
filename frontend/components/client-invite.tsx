"use client";
import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { mutate } from "@/lib/browser-api";
export function ClientInvite({
  clientId,
  email,
}: {
  clientId: string;
  email?: string;
}) {
  const router = useRouter(),
    [link, setLink] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function issue(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setLink("");
    setError("");
    const d = new FormData(e.currentTarget);
    try {
      const r = await mutate("/clients/" + clientId + "/invitations", "POST", {
        email: d.get("email"),
        role: d.get("role"),
      });
      setLink(location.origin + "/accept-invitation#" + r.token);
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not issue invitation");
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={issue} className="space-y-3">
      <h3>Invite client contact</h3>
      <label>
        Invitation email
        <input type="email" name="email" defaultValue={email} required />
      </label>
      <label>
        Client role
        <select name="role">
          <option value="client_admin">Client Admin</option>
          <option value="client_member">Client Member</option>
        </select>
      </label>
      <Button disabled={busy}>Create invitation</Button>
      {link && (
        <label>
          Private invitation link
          <input readOnly value={link} onFocus={(e) => e.target.select()} />
        </label>
      )}
      <p role="status">{error}</p>
    </form>
  );
}
