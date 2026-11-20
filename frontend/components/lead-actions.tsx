"use client";
import { ClientInvite } from "@/components/client-invite";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { mutate } from "@/lib/browser-api";
import type { Lead } from "@/lib/intake";
import { Button } from "@/components/ui/button";
export function LeadActions({
  lead,
  staff,
}: {
  lead: Lead;
  staff: { id: string; full_name: string }[];
}) {
  const router = useRouter();
  const [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setMessage("");
    try {
      await fn();
      router.refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }
  function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const d = new FormData(e.currentTarget);
    void run(async () => {
      await mutate("/leads/" + lead.id, "PATCH", {
        status: d.get("status"),
        notes: d.get("notes"),
      });
      setMessage("Review saved");
    });
  }
  function convert(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!window.confirm("Convert " + lead.company_name + " to a client?"))
      return;
    const name = String(
      new FormData(e.currentTarget).get("project") || "",
    ).trim();
    void run(async () => {
      await mutate("/leads/" + lead.id + "/convert", "POST", {
        create_initial_project: !!name,
        initial_project_name: name || null,
      });
      setMessage("Client created");
    });
  }
  return (
    <div className="space-y-6">
      {lead.status !== "converted" && lead.status !== "rejected" && (
        <>
          <form onSubmit={save} className="space-y-3">
            <h3>Agency review</h3>
            <label>
              Lead status
              <select name="status" defaultValue={lead.status}>
                {["new", "contacted", "qualified", "proposal_sent"].map((s) => (
                  <option key={s} value={s}>
                    {s.replace("_", " ")}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Internal notes
              <textarea
                name="notes"
                defaultValue={lead.notes || ""}
                maxLength={5000}
              />
            </label>
            <Button disabled={busy}>Save review</Button>
          </form>
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              const user_id =
                new FormData(e.currentTarget).get("owner") || null;
              void run(async () => {
                await mutate("/leads/" + lead.id + "/assign", "POST", {
                  user_id,
                });
                setMessage("Owner updated");
              });
            }}
          >
            <label>
              Lead owner
              <select name="owner" defaultValue={lead.assigned_to || ""}>
                <option value="">Unassigned</option>
                {staff.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.full_name}
                  </option>
                ))}
              </select>
            </label>
            <Button disabled={busy}>Save owner</Button>
          </form>
          {["qualified", "proposal_sent"].includes(lead.status) && (
            <form onSubmit={convert} className="space-y-3">
              <h3>Convert to client</h3>
              <label>
                Initial project name (optional)
                <input name="project" maxLength={200} />
              </label>
              <Button disabled={busy}>Convert lead</Button>
            </form>
          )}
          <button
            disabled={busy}
            onClick={() =>
              void run(async () => {
                await mutate("/leads/" + lead.id + "/reject", "POST");
              })
            }
          >
            Reject lead
          </button>
        </>
      )}
      {lead.converted_client_id && (
        <ClientInvite clientId={lead.converted_client_id} email={lead.email} />
      )}
      <p role="status">{message}</p>
    </div>
  );
}
