import Link from "next/link";
import { notFound } from "next/navigation";
import { getApi, requirePortal } from "@/lib/server-api";
import { canManage } from "@/lib/projects";
import { RunEvaluation } from "@/components/evaluation-actions";
type Run = {
  id: string;
  provider: string;
  model: string;
  dataset_version: string;
  prompt_version: string;
  created_at: string;
  aggregates: { passed: number; total: number };
};
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>;
}) {
  const me = await requirePortal("admin");
  if (!canManage(me.agency_roles)) notFound();
  const page = Math.max(1, Number((await searchParams).page) || 1);
  const rows = (await getApi<Run[]>("/admin/evaluations?page=" + page)) ?? [];
  return (
    <article className="space-y-5">
      <h2>AI evaluations</h2>
      <p>
        Run the versioned synthetic briefs through all five fixture services.
        Human reviewers assess creative quality separately.
      </p>
      <RunEvaluation />
      <section>
        <h3>Evaluation history</h3>
        {!rows.length && <p>No evaluations recorded.</p>}
        {rows.map((r) => (
          <Link
            key={r.id}
            href={"/admin/evaluations/" + r.id}
            className="my-2 flex flex-wrap justify-between gap-3 rounded-lg border p-4"
          >
            <strong>{r.dataset_version}</strong>
            <span>
              {r.model} · {r.prompt_version}
            </span>
            <span>
              {r.aggregates.passed} / {r.aggregates.total} checks passed
            </span>
            <time>{r.created_at.slice(0, 19).replace("T", " ")} UTC</time>
          </Link>
        ))}
      </section>
      <nav className="flex gap-4">
        {page > 1 && (
          <Link href={"?page=" + (page - 1)}>Previous evaluations</Link>
        )}
        {rows.length === 30 && (
          <Link href={"?page=" + (page + 1)}>Next evaluations</Link>
        )}
      </nav>
    </article>
  );
}
