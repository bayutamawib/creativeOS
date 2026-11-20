"use client";
import { useState, useEffect, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { mutate } from "@/lib/browser-api";
import { Button } from "@/components/ui/button";

export function GenerateForm() {
  const [choices, setChoices] = useState<{ id: string; name: string }[]>([]),
    [project, setProject] = useState(""),
    [q, search] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const router = useRouter();
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/v1/projects?portal=agency&q=" + encodeURIComponent(q), {
      signal: controller.signal,
    })
      .then(async (r) => {
        if (!r.ok) throw Error();
        const rows = (await r.json()).data;
        setChoices(rows);
        setProject(rows[0]?.id ?? "");
      })
      .catch(() => {
        if (!controller.signal.aborted) setError("Could not load projects");
      });
    return () => controller.abort();
  }, [q]);
  async function generate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data = Object.fromEntries(new FormData(e.currentTarget));
      const row = await mutate(
        "/projects/" + project + "/reports/generate",
        "POST",
        data,
      );
      router.push("/admin/reports/" + row.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={generate} className="space-y-3 rounded-lg border p-4">
      <h3>Generate a project report</h3>
      <div className="grid gap-3 md:grid-cols-2">
        <label>
          Find project
          <input value={q} onChange={(e) => search(e.target.value)} />
        </label>
        <label>
          Reporting project
          <select
            required
            value={project}
            onChange={(e) => setProject(e.target.value)}
          >
            {choices.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Period start
          <input type="date" required name="period_start" />
        </label>
        <label>
          Period end
          <input type="date" required name="period_end" />
        </label>
      </div>
      <Button disabled={!project || busy}>Generate report</Button>
      <p role="status">{error}</p>
    </form>
  );
}
type Editable = {
  id: string;
  version: number;
  status: string;
  narrative: string | null;
  project_id: string;
  report_type: string;
  period_start: string;
  period_end: string;
};
export function ReportActions({
  report: r,
  manage,
}: {
  report: Editable;
  manage: boolean;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [draft, setDraft] = useState(r.narrative ?? "");
  const router = useRouter();
  useEffect(() => {
    if (r.status !== "generating") return;
    const t = setInterval(() => router.refresh(), 1500);
    return () => clearInterval(t);
  }, [r.status, router]);
  if (!manage || r.status === "published" || r.status === "generating")
    return null;
  async function act(action: string) {
    setBusy(true);
    setError("");
    try {
      if (action === "retry")
        await mutate(
          "/projects/" + r.project_id + "/reports/generate",
          "POST",
          {
            report_type: r.report_type,
            period_start: r.period_start,
            period_end: r.period_end,
          },
        );
      else
        await mutate(
          "/reports/" + r.id + (action ? "/" + action : ""),
          action ? "POST" : "PATCH",
          action
            ? { version: r.version }
            : { narrative: draft, version: r.version },
        );
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="space-y-3 rounded-lg border p-4">
      <h3>Agency review</h3>
      {r.status === "failed" ? (
        <Button disabled={busy} onClick={() => act("retry")}>
          Retry summary
        </Button>
      ) : (
        <>
          <label>
            Draft narrative
            <textarea
              rows={5}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
            />
          </label>
          <div className="flex gap-3">
            <Button
              disabled={busy || draft === r.narrative}
              onClick={() => act("")}
            >
              Save narrative
            </Button>
            <Button
              disabled={busy || draft !== r.narrative}
              onClick={() =>
                act(r.status === "draft" ? "submit-for-review" : "publish")
              }
            >
              {r.status === "draft" ? "Submit for review" : "Publish to client"}
            </Button>
          </div>
        </>
      )}
      <p role="status">{error}</p>
    </section>
  );
}
