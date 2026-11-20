"use client";
import Link from "next/link";
import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import type { Studio, Json, Job } from "@/lib/studio";
import { mutate } from "@/lib/browser-api";
function label(value: string) {
  return value.replaceAll("_", " ");
}
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
                {data.jobs.map((j) => (
                  <article key={j.id} className="border-b border-border py-2">
                    <strong>{label(j.generation_type)}</strong> · {j.status}
                    <p className="text-xs">
                      {j.provider} / {j.model} · {j.prompt_version} · Attempt{" "}
                      {j.attempt}
                    </p>
                    {j.error_code && <p>{label(j.error_code)}</p>}
                    {j.status === "failed" &&
                      button("Retry " + label(j.generation_type), () =>
                        retry(j),
                      )}
                    {j.output && (
                      <details>
                        <summary>Validated output</summary>
                        <Value value={j.output} />
                      </details>
                    )}
                  </article>
                ))}
              </section>
              {["direction", "plan_item"].map((kind) => (
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
              {data.items.map((item) => (
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
