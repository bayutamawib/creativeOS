import Link from "next/link";
import { notFound } from "next/navigation";
import { getApi, requirePortal } from "@/lib/server-api";
import { canManage } from "@/lib/projects";
import { ReviewOutput, type Rubric } from "@/components/evaluation-actions";
type Case = {
  id: string;
  case_key: string;
  service: string;
  passed: boolean;
  sample: object;
  output: object | null;
  checks: Record<string, unknown>;
  latency_ms: number;
  my_review: Rubric | null;
};
type Result = {
  id: string;
  provider: string;
  model: string;
  dataset_version: string;
  dataset_hash: string;
  prompt_version: string;
  aggregates: {
    attempted: number;
    outputs: number;
    schema_valid: number;
    required_complete: number;
    grounding_passed: number;
    controls: number;
    controls_passed: number;
    total: number;
    passed: number;
    generation_latency_ms: number;
    generation_success_rate: number;
  };
  human: {
    reviewed: number;
    mean_rubric_score: number | null;
    acceptance_rate: number | null;
    revision_rate: number | null;
  };
  cases: Case[];
};
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const me = await requirePortal("admin");
  if (!canManage(me.agency_roles)) notFound();
  const id = (await params).id;
  const r = await getApi<Result>("/admin/evaluations/" + id);
  if (!r) notFound();
  const a = r.aggregates;
  return (
    <article className="space-y-5">
      <Link href="/admin/evaluations">Evaluation history</Link>
      <h2>Evaluation results</h2>
      <p>
        {r.dataset_version} · {r.provider} / {r.model} · {r.prompt_version}
      </p>
      <details>
        <summary>Execution provenance</summary>
        <p className="break-all">Dataset SHA-256 {r.dataset_hash}</p>
        <p>
          Run {r.id} · Total fixture execution time {a.generation_latency_ms} ms
          · Token usage unavailable
        </p>
      </details>
      <h3>
        {a.passed} / {a.total} automated cases passed
      </h3>
      <dl className="grid gap-3 md:grid-cols-3">
        {[
          ["Schema-valid outputs", a.schema_valid + " / " + a.attempted],
          ["Required fields complete", a.required_complete + " / " + a.outputs],
          ["Input grounding checks", a.grounding_passed + " / " + a.outputs],
          ["Negative controls", a.controls_passed + " / " + a.controls],
          [
            "Generation success",
            (100 * a.generation_success_rate).toFixed(0) + "%",
          ],
        ].map(([k, v]) => (
          <div className="rounded-lg border p-4" key={k}>
            <dt>{k}</dt>
            <dd className="text-xl">{v}</dd>
          </div>
        ))}
      </dl>
      <section>
        <h3>Human assessment</h3>
        {r.human.reviewed === 0 ? (
          <p>No human scores recorded. Semantic quality is unassessed.</p>
        ) : (
          <p>
            {r.human.reviewed} outputs reviewed · Mean rubric{" "}
            {r.human.mean_rubric_score?.toFixed(2)} / 5 · Acceptance{" "}
            {((r.human.acceptance_rate ?? 0) * 100).toFixed(0)}% · Revision
            required {((r.human.revision_rate ?? 0) * 100).toFixed(0)}%
          </p>
        )}
      </section>
      <section>
        <h3>Individual outcomes</h3>
        {r.cases.map((c) => (
          <details key={c.id} className="my-2 rounded-lg border p-3">
            <summary>
              {c.case_key} · {c.passed ? "Passed" : "Failed"}
            </summary>
            <div className="space-y-3 py-3">
              {[
                ["Checks", c.checks],
                ["Synthetic input", c.sample],
                ["Output", c.output],
              ]
                .filter(([, v]) => v)
                .map(([k, v]) => (
                  <section key={String(k)}>
                    <h4>{String(k)}</h4>
                    <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded bg-slate-50 p-3 text-sm">
                      {JSON.stringify(v, null, 2)}
                    </pre>
                  </section>
                ))}
              {c.output && (
                <ReviewOutput
                  review={c.my_review}
                  path={
                    "/admin/evaluations/" + id + "/cases/" + c.id + "/review"
                  }
                />
              )}
            </div>
          </details>
        ))}
      </section>
    </article>
  );
}
