import Link from "next/link";
import { notFound } from "next/navigation";
import { getApi, requirePortal } from "@/lib/server-api";
import { canManage } from "@/lib/projects";
import { OperationForm } from "@/components/operation-form";

const tabs = {
  outbox: "Outbox events",
  "workflow-runs": "Workflow runs",
  "generation-jobs": "Generation jobs",
  "delivery-attempts": "Delivery attempts",
};
type Row = {
  id: string;
  kind?: string;
  channel?: string;
  workflow?: string;
  project_id?: string;
  provider?: string;
  model?: string;
  status: string;
  attempt: number;
  execution?: string;
  event_id?: string;
  resource_id?: string;
  run_id?: string;
  report_id?: string;
  error?: string;
  duration_ms?: number;
  retryable?: boolean;
  created_at?: string;
  started_at?: string;
};
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ view?: string; page?: string; state?: string }>;
}) {
  const me = await requirePortal("admin");
  if (!canManage(me.agency_roles)) notFound();
  const query = await searchParams,
    tab =
      query.view && Object.hasOwn(tabs, query.view)
        ? (query.view as keyof typeof tabs)
        : "outbox",
    page = Math.max(1, Number(query.page) || 1);
  const filter =
    query.state === "failed" || query.state === "uncertain"
      ? "&state=" + query.state
      : "";
  const rows =
    (await getApi<Row[]>("/admin/" + tab + "?page=" + page + filter)) ?? [];
  return (
    <section className="space-y-5">
      <header>
        <h2>Automation activity</h2>
      </header>
      <nav aria-label="Activity views" className="flex flex-wrap gap-4">
        {Object.entries(tabs).map(([key, label]) => (
          <Link
            key={key}
            aria-current={key === tab ? "page" : undefined}
            className={key === tab ? "font-semibold underline" : ""}
            href={"?view=" + key}
          >
            {label}
          </Link>
        ))}
        <Link href="/admin/evaluations">AI evaluations</Link>
      </nav>
      <h3>{tabs[tab]}</h3>
      <nav aria-label="Filter activity" className="flex gap-4">
        <Link href={"?view=" + tab}>All states</Link>
        <Link href={"?view=" + tab + "&state=failed"}>Failed</Link>
        {tab === "delivery-attempts" && (
          <Link href={"?view=" + tab + "&state=uncertain"}>Uncertain</Link>
        )}
      </nav>
      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr>
              {[
                "Activity",
                "Recorded",
                "State",
                "Attempt",
                "Duration",
                "Correlation",
                "Failure / recovery",
              ].map((t) => (
                <th key={t} className="pr-4 py-2">
                  {t}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const event = tab === "outbox" ? r.id : r.event_id;
              return (
                <tr key={r.id} className="border-t align-top">
                  <td className="py-3 pr-4">
                    {r.kind || r.workflow || r.channel}
                  </td>
                  <td className="pr-4">
                    {(r.created_at || r.started_at)
                      ?.slice(0, 19)
                      .replace("T", " ") || "—"}
                    {r.created_at || r.started_at ? " UTC" : ""}
                  </td>
                  <td>{r.status}</td>
                  <td>{r.attempt}</td>
                  <td>{r.duration_ms == null ? "—" : r.duration_ms + " ms"}</td>
                  <td className="pr-4 break-all">
                    {event ? (
                      <Link href={"/admin/automation/" + event}>
                        {r.execution ? "n8n " + r.execution : event}
                      </Link>
                    ) : (
                      r.id
                    )}
                    {r.provider && (
                      <small className="block">
                        {r.provider} / {r.model}
                      </small>
                    )}
                  </td>
                  <td>
                    {r.error || "—"}
                    {r.retryable && (
                      <OperationForm
                        path={"/admin/" + tab + "/" + r.id + "/retry"}
                        label="Queue retry"
                      />
                    )}
                    {r.report_id && (
                      <Link href={"/admin/reports/" + r.report_id}>
                        Open report
                      </Link>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {!rows.length && <p>No activity on this page.</p>}
      <nav className="flex gap-4">
        {page > 1 && (
          <Link href={"?view=" + tab + filter + "&page=" + (page - 1)}>
            Previous page
          </Link>
        )}
        {rows.length === 30 && (
          <Link href={"?view=" + tab + filter + "&page=" + (page + 1)}>
            Next page
          </Link>
        )}
      </nav>
    </section>
  );
}
