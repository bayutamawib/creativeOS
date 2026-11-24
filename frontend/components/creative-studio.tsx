"use client";
import Link from "next/link";
import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import type { Studio, Json, Job } from "@/lib/studio";
import { mutate } from "@/lib/browser-api";
function label(value: string) {
  return value.replaceAll("_", " ");
}
const stages = [
  ["brief_analysis", "Brief Analysis"],
  ["creative_strategy", "Creative Strategy"],
  ["content_plan", "Content Plan"],
  ["copywriting", "Copywriting"],
] as const;
function Value({ value }: { value: Json }) {
  if (value === null) return <span>—</span>;
  if (Array.isArray(value))
    return (
      <ul className="list-disc space-y-1 pl-5">
        {value.map((v, i) => (
          <li key={i}>
            <Value value={v} />
          </li>
        ))}
      </ul>
    );
  if (typeof value === "object")
    return (
      <dl className="space-y-2">
        {Object.entries(value)
          .filter(([, v]) => v !== null && (!Array.isArray(v) || v.length > 0))
          .map(([k, v]) => (
            <div key={k}>
              <dt className="text-xs font-semibold uppercase text-slate-600">
                {label(k)}
              </dt>
              <dd>
                <Value value={v} />
              </dd>
            </div>
          ))}
      </dl>
    );
  return <span>{String(value)}</span>;
}
export function CreativeStudio({
  initial,
  manager,
}: {
  initial: Studio;
  manager: boolean;
}) {
  const [data, setData] = useState(initial),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [retryKeys, setRetryKeys] = useState<Record<string, string>>({});
  const [stage, setStage] = useState<(typeof stages)[number][0]>("brief_analysis");
  const brief = data.brief,
    base = "/briefs/" + brief.id;
  const watching =
    data.jobs.some((j) => ["pending", "running"].includes(j.status)) ||
    data.automation.some((w) => ["pending", "processing"].includes(w.delivery));
  async function refresh(signal?: AbortSignal) {
    const res = await fetch("/api/v1" + base + "/studio", {
      cache: "no-store",
      signal,
    });
    if (!res.ok) throw Error("Unable to refresh the studio");
    setData((await res.json()).data);
  }
  useEffect(() => {
    if (!watching) return;
    const c = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const r = await fetch("/api/v1/briefs/" + brief.id + "/studio", {
          cache: "no-store",
          signal: c.signal,
        });
        if (!r.ok) throw Error();
        setData((await r.json()).data);
      } catch {
        if (!c.signal.aborted) setError("Could not refresh generation status");
      }
      if (!c.signal.aborted) timer = setTimeout(poll, 1200);
    }
    timer = setTimeout(poll, 1000);
    return () => {
      c.abort();
      clearTimeout(timer);
    };
  }, [brief.id, watching]);
  async function post(path: string, body: unknown = {}, generation = false) {
    setBusy(true);
    setError("");
    const signature = path + JSON.stringify(body);
    const key = retryKeys[signature] || crypto.randomUUID();
    try {
      await mutate(
        path,
        "POST",
        body,
        generation ? { "Idempotency-Key": key } : undefined,
      );
      setRetryKeys((prev) => {
        const next = { ...prev };
        delete next[signature];
        return next;
      });
      await refresh();
    } catch (e) {
      if (generation) setRetryKeys((prev) => ({ ...prev, [signature]: key }));
      setError(e instanceof Error ? e.message : "Operation failed");
    } finally {
      setBusy(false);
    }
  }
  const button = (name: string, fn: () => void) => (
    <Button disabled={busy} onClick={fn}>
      {name}
    </Button>
  );
  const generate = (path: string, opts: object = {}) =>
    post(path, { snapshot_id: brief.snapshot_id, ...opts }, true);
  const selected = data.proposals.find(
    (p) => p.kind === "direction" && p.decision === "approved",
  );
  const analysis = data.jobs.find(
    (j) => j.generation_type === "brief_analysis" && j.status === "completed",
  );
  const stageJobs = data.jobs.filter((j) => j.generation_type === stage);
  const latestJob = stageJobs[0];
  const olderJobs = stageJobs.slice(1);
  const hasCritical = (j: Job | undefined) =>
    j?.quality_findings?.disposition === "critical";
  const statusText = (j: Job | undefined) =>
    !j ? "Not generated" : hasCritical(j) ? "Needs review · critical findings" : j.status === "completed" ? "Generated" : label(j.status);
  const statusClass = (j: Job | undefined) =>
    !j || hasCritical(j) ? "border-amber-300 bg-amber-50 text-amber-950" : j.status === "completed" ? "border-emerald-200 bg-emerald-50 text-emerald-950" : "border-border bg-slate-50";
  const retry = (j: Job) => {
    if (j.generation_type === "copywriting") {
      const item = data.items.find(
        (i) => i.current_revision_id === j.revision_id,
      );
      if (item)
        void generate("/content-items/" + item.id + "/generate", {
          revision_id: j.revision_id,
          feedback: j.parameters.feedback,
        });
    } else {
      const route =
        j.generation_type === "brief_analysis"
          ? "analyze"
          : j.generation_type === "creative_strategy"
            ? "generate-creative-direction"
            : "generate-content-plan";
      void generate(
        base + "/" + route,
        j.generation_type === "content_plan"
          ? {
              direction_proposal_id: j.direction_id,
              channels: j.parameters.channels,
              target_count: j.parameters.target_count,
            }
          : {},
      );
    }
  };
  return (
    <div className="space-y-6">
      <p role="alert">{error}</p>
      <header>
        <h2>{brief.title}</h2>
        <p>
          Brief version {brief.version} · {label(brief.status)} ·{" "}
          {data.provider === "fixture"
            ? "Deterministic fixture provider"
            : data.provider + " provider"}
        </p>
      </header>
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(12rem,1fr)_3fr]">
        <aside className="space-y-4 rounded-lg bg-slate-50 p-4">
          <h3>Approved context</h3>
          <p>{brief.objective}</p>
          {brief.restrictions && <p>Restrictions · {brief.restrictions}</p>}
          <Value value={data.brand} />
          <Link
            className="text-primary"
            href={
              "/admin/briefs?project=" + brief.project_id + "&brief=" + brief.id
            }
          >
            Open brief
          </Link>
        </aside>
        <div className="space-y-6">
          {!brief.snapshot_id ? (
            <p>Approve the current brief version to start creative work.</p>
          ) : (
            <>
              <nav aria-label="Creative Studio stages" className="grid gap-2 sm:grid-cols-4">
                {stages.map(([id, name], index) => (
                  <button key={id} type="button" aria-current={stage === id ? "step" : undefined} onClick={() => setStage(id)} className={`rounded-lg border p-3 text-left ${stage === id ? "border-primary bg-primary/10" : "border-border bg-white"}`}>
                    <span className="text-xs font-semibold uppercase text-slate-500">Step {index + 1}</span>
                    <span className="block font-semibold">{name}</span>
                    <span className="text-xs text-slate-600">{statusText(data.jobs.find((j) => j.generation_type === id))}</span>
                  </button>
                ))}
              </nav>
              <section className="space-y-3">
                <h3>Generation history</h3>
                <div className="flex flex-wrap gap-2">
                  {button(
                    "Analyze brief",
                    () => void generate(base + "/analyze"),
                  )}
                  {analysis &&
                    button(
                      "Generate directions",
                      () =>
                        void generate(base + "/generate-creative-direction"),
                    )}
                  {selected &&
                    button(
                      "Generate content plan",
                      () =>
                        void generate(base + "/generate-content-plan", {
                          direction_proposal_id: selected.id,
                        }),
                    )}
                </div>
                {data.automation.map((w) => (
                  <p className="text-sm text-slate-600" key={w.event}>
                    {label(w.event)} · {w.run || w.delivery}
                    {w.execution_id && " · n8n #" + w.execution_id}
                  </p>
                ))}
                {latestJob ? <article className={`rounded-lg border p-4 ${statusClass(latestJob)}`}>
                    <strong>{statusText(latestJob)}</strong>
                    <p className="text-xs">
                      {latestJob.provider} / {latestJob.model} · {latestJob.prompt_version} · Attempt {latestJob.attempt}
                    </p>
                    {latestJob.error_code && <p>{label(latestJob.error_code)}</p>}
                    {latestJob.quality_findings && <details><summary>Quality findings</summary><Value value={latestJob.quality_findings} /></details>}
                    {latestJob.status === "failed" && button("Retry " + label(latestJob.generation_type), () => retry(latestJob))}
                    {latestJob.output && (
                      <details>
                        <summary>Validated output</summary>
                        <Value value={latestJob.output} />
                      </details>
                    )}
                  </article> : <p className="rounded-lg border border-dashed border-border p-6 text-slate-600">No generation has been created for this stage yet.</p>}
                {olderJobs.length > 0 && <details>
                  <summary className="cursor-pointer font-semibold">Older generation history ({olderJobs.length})</summary>
                  <div className="mt-3 space-y-2">{olderJobs.map((j) => <article key={j.id} className={`rounded-lg border p-3 ${statusClass(j)}`}><strong>{statusText(j)}</strong><p className="text-xs">{j.provider} / {j.model} · {j.prompt_version} · Attempt {j.attempt}</p>{j.quality_findings && <details><summary>Quality findings</summary><Value value={j.quality_findings} /></details>}{j.output && <details><summary>Validated output</summary><Value value={j.output} /></details>}</article>)}</div>
                </details>}
              </section>
              {["direction", "plan_item"].filter((kind) => stage === (kind === "direction" ? "creative_strategy" : "content_plan")).map((kind) => (
                <section key={kind} className="space-y-3">
                  <h3>
                    {kind === "direction"
                      ? "Creative directions"
                      : "Content plan"}
                  </h3>
                  {data.proposals
                    .filter((p) => p.kind === kind)
                    .map((p) => (
                      <article
                        key={p.id}
                        className="space-y-3 rounded-lg border border-border p-4"
                      >
                        <h4 className="text-lg font-semibold">
                          {String(p.payload.concept_name || p.payload.title)}
                        </h4>
                        <p>
                          {String(
                            p.payload.strategic_rationale ||
                              p.payload.key_message,
                          )}
                        </p>
                        <p className="text-sm">
                          {label(p.decision)}
                          {p.payload.channel ? " · " + p.payload.channel : ""}
                        </p>
                        <details>
                          <summary>Proposal details</summary>
                          <Value value={p.payload} />
                        </details>
                        <div className="flex flex-wrap gap-2">
                          {manager && p.decision === "pending" && (
                            <>
                              {(kind !== "direction" || !selected) &&
                                button(
                                  kind === "direction"
                                    ? "Select direction"
                                    : "Select plan item",
                                  () =>
                                    void post(
                                      "/proposals/" + p.id + "/approve",
                                    ),
                                )}
                              {button(
                                "Reject proposal",
                                () =>
                                  void post("/proposals/" + p.id + "/reject"),
                              )}
                            </>
                          )}
                          {kind === "plan_item" &&
                            p.decision === "approved" &&
                            !data.items.some(
                              (i) => i.source_proposal_id === p.id,
                            ) &&
                            button(
                              "Create draft deliverable",
                              () =>
                                void post(
                                  "/projects/" +
                                    brief.project_id +
                                    "/content-items",
                                  { proposal_id: p.id },
                                ),
                            )}
                        </div>
                      </article>
                    ))}
                </section>
              ))}
              {stage === "copywriting" && data.items.map((item) => (
                <section
                  key={item.id}
                  className="space-y-3 rounded-lg border border-border p-4"
                >
                  <h3>{item.title}</h3>
                  <p>Draft deliverable · Revision {item.revision_number}</p>
                  <details>
                    <summary>Current draft</summary>
                    <Value value={item.content} />
                  </details>
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      void generate("/content-items/" + item.id + "/generate", {
                        revision_id: item.current_revision_id,
                        feedback:
                          new FormData(e.currentTarget).get("feedback") || null,
                      });
                    }}
                  >
                    <label>
                      Copywriting feedback
                      <textarea name="feedback" maxLength={4000} />
                    </label>
                    <Button disabled={busy}>Suggest copy</Button>
                  </form>
                  {data.jobs
                    .filter(
                      (j) =>
                        j.revision_id === item.current_revision_id &&
                        j.status === "completed" &&
                        j.output,
                    )
                    .map((j) => (
                      <div key={j.id}>
                        <Value value={j.output} />
                        {button(
                          "Save copy as revision",
                          () =>
                            void post(
                              "/content-items/" + item.id + "/revisions",
                              { generation_id: j.id },
                            ),
                        )}
                      </div>
                    ))}
                </section>
              ))}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
