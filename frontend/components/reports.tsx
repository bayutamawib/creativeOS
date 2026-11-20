import Link from "next/link";
import { getApi, requirePortal } from "@/lib/server-api";
import { canManage } from "@/lib/projects";
import { notFound } from "next/navigation";
import { ReportActions, GenerateForm } from "@/components/report-actions";

type Portal = "admin" | "client";
type Report = {
  id: string;
  project_name: string;
  project_id: string;
  report_type: string;
  period_start: string;
  period_end: string;
  status: string;
  version: number;
  metrics: Record<string, string | number>;
  provenance: { timezone: string; captured_at: string };
  narrative: string | null;
  published_at: string | null;
};
type Count = { label: string; count: number };
const words = (name: string) => name.replaceAll("_", " ");
export async function ReportList({
  portal,
  page,
}: {
  portal: Portal;
  page: number;
}) {
  const me = await requirePortal(portal),
    manage = portal === "admin" && canManage(me.agency_roles);
  const mode = portal === "admin" ? "agency" : "client";
  const rows =
    (await getApi<Report[]>("/reports?portal=" + mode + "&page=" + page)) ?? [];
  const counts = manage
    ? await Promise.all(
        ["operations", "workload", "workflows"].map((k) =>
          getApi<Count[]>("/agency/reports/" + k),
        ),
      )
    : [];
  return (
    <div className="space-y-6">
      <header>
        <h2>Project reports</h2>
      </header>
      {manage && (
        <>
          <div className="grid gap-3 md:grid-cols-3">
            {[
              "Projects by status",
              "Open task assignments",
              "Workflow runs",
            ].map((label, i) => (
              <section className="rounded-lg border p-4" key={label}>
                <h3>{label}</h3>
                {counts[i]?.length ? (
                  counts[i]?.map((c, j) => (
                    <p key={j} className="flex justify-between gap-2">
                      <span>{words(c.label)}</span>
                      <strong>{c.count}</strong>
                    </p>
                  ))
                ) : (
                  <p>No activity</p>
                )}
              </section>
            ))}
          </div>
          <GenerateForm />
        </>
      )}
      <section>
        <h3>
          {portal === "client" ? "Published reports" : "Reporting periods"}
        </h3>
        {rows.length === 0 && <p>No reports available.</p>}
        {rows.map((r) => (
          <Link
            className="my-2 flex flex-wrap justify-between gap-2 rounded-lg border p-4"
            key={r.id}
            href={"/" + portal + "/reports/" + r.id}
          >
            <strong>{r.project_name}</strong>
            <span>
              {r.period_start} – {r.period_end}
            </span>
            <span>{words(r.status)}</span>
          </Link>
        ))}
      </section>
      <nav className="flex gap-4">
        {page > 1 && <Link href={"?page=" + (page - 1)}>Previous reports</Link>}
        {rows.length === 50 && (
          <Link href={"?page=" + (page + 1)}>Next reports</Link>
        )}
      </nav>
    </div>
  );
}
export async function ReportDetail({
  portal,
  id,
}: {
  portal: Portal;
  id: string;
}) {
  const me = await requirePortal(portal),
    mode = portal === "admin" ? "agency" : "client";
  const r = await getApi<Report>("/reports/" + id + "?portal=" + mode);
  if (!r) notFound();
  const p = await getApi<{ name: string }>(
    "/projects/" + r.project_id + "?portal=" + mode,
  );
  return (
    <article className="space-y-5">
      <Link href={"/" + portal + "/reports"}>All reports</Link>
      <header>
        <h2>{p?.name} report</h2>
        <p>
          {r.period_start} – {r.period_end} · {words(r.status)}
        </p>
      </header>
      <section>
        <h3>Reporting period</h3>
        <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {Object.entries(r.metrics)
            .filter(
              ([k]) => k === "completed_tasks" || k.endsWith("_in_period"),
            )
            .map(([k, v]) => (
              <div key={k} className="rounded-lg border p-3">
                <dt>{words(k)}</dt>
                <dd className="text-xl font-semibold">{v}</dd>
              </div>
            ))}
        </dl>
      </section>
      <section>
        <h3>Project snapshot</h3>
        <p>
          Captured{" "}
          {new Date(r.provenance.captured_at).toLocaleString("en-GB", {
            timeZone: r.provenance.timezone,
          })}{" "}
          · {r.provenance.timezone}
        </p>
        <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {Object.entries(r.metrics)
            .filter(
              ([k]) =>
                k !== "period" &&
                k !== "completed_tasks" &&
                !k.endsWith("_in_period"),
            )
            .map(([k, v]) => (
              <div key={k} className="rounded-lg border p-3">
                <dt>{words(k)}</dt>
                <dd>{v}</dd>
              </div>
            ))}
        </dl>
      </section>
      <section>
        <h3>Report narrative</h3>
        <p className="whitespace-pre-line">
          {r.narrative ??
            (r.status === "failed"
              ? "Summary generation failed. The verified metrics are available."
              : "Generating a summary from the verified metrics…")}
        </p>
      </section>
      <a href={"/api/v1/reports/" + id + "/download?portal=" + mode} download>
        Download report (JSON)
      </a>
      {portal === "admin" && (
        <ReportActions
          key={r.status + "-" + r.version}
          report={r}
          manage={canManage(me.agency_roles)}
        />
      )}
    </article>
  );
}
