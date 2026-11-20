import Link from "next/link";
import { notFound } from "next/navigation";
import { getApi, requirePortal } from "@/lib/server-api";
import type { Project } from "@/lib/projects";
import type { Asset, Brief } from "@/lib/briefs";
import { BriefWorkspace } from "./brief-workspace";
export type BriefQuery = { project?: string; brief?: string; page?: string };
export async function BriefPage({
  portal,
  query,
}: {
  portal: "agency" | "client";
  query: BriefQuery;
}) {
  const section = portal === "agency" ? "admin" : "client",
    me = await requirePortal(section);
  const projects: Project[] = [];
  for (let page = 1; ; page++) {
    const batch =
      (await getApi<Project[]>(
        "/projects?portal=" + portal + "&page=" + page,
      )) || [];
    projects.push(...batch);
    if (batch.length < 50) break;
  }
  const p = query.project
    ? projects.find((p) => p.id === query.project)
    : projects[0];
  if (query.project && !p) notFound();
  const suffix = "?portal=" + portal;
  const briefs = p
    ? await getApi<Brief[]>(
        "/projects/" +
          p.id +
          "/briefs" +
          suffix +
          "&page=" +
          Math.max(1, Number(query.page) || 1),
      )
    : [];
  const files: Asset[] = [];
  if (p) {
    for (let page = 1; ; page++) {
      const batch =
        (await getApi<Asset[]>(
          "/files" + suffix + "&project_id=" + p.id + "&page=" + page,
        )) || [];
      files.push(...batch);
      if (batch.length < 50) break;
    }
  }
  const current = query.brief
    ? await getApi<Brief>("/briefs/" + encodeURIComponent(query.brief) + suffix)
    : null;
  if (query.brief && (!current || current.project_id !== p?.id)) notFound();
  const approvals = current
    ? await getApi<
        {
          id: string;
          version: number;
          approved_at: string;
          fields: { title: string; objective: string };
          attachments: { id: string; name: string }[];
        }[]
      >("/briefs/" + current.id + "/snapshots" + suffix)
    : [];
  return (
    <div className="space-y-5">
      <h2>Creative briefs</h2>
      <form className="flex flex-wrap items-end gap-3">
        <label>
          Project
          <select name="project" defaultValue={p?.id}>
            {projects.map((x) => (
              <option key={x.id} value={x.id}>
                {x.name}
              </option>
            ))}
          </select>
        </label>
        <button className="text-primary">Open project</button>
      </form>
      {p ? (
        <div className="grid gap-6 lg:grid-cols-[15rem_1fr]">
          <aside className="space-y-3">
            <Link href={"?project=" + p.id}>New brief</Link>
            <ul>
              {briefs?.map((b) => (
                <li key={b.id} className="border-b border-border py-2">
                  <Link href={"?project=" + p.id + "&brief=" + b.id}>
                    {b.title}
                  </Link>
                  <p className="text-xs">{b.status.replaceAll("_", " ")}</p>
                </li>
              ))}
            </ul>
            {Number(query.page) > 1 && (
              <Link
                href={"?project=" + p.id + "&page=" + (Number(query.page) - 1)}
              >
                Previous
              </Link>
            )}
            {briefs?.length === 50 && (
              <Link
                href={
                  "?project=" + p.id + "&page=" + (Number(query.page || 1) + 1)
                }
              >
                Next
              </Link>
            )}
          </aside>
          <div className="space-y-4">
            <BriefWorkspace
              key={p.id + "-" + (current?.id || "new")}
              project={p.id}
              portal={portal}
              brief={current}
              files={files}
              canSubmit={
                portal === "client" &&
                me.client_memberships.some(
                  (m) =>
                    m.client_id === p.client_id && m.role === "client_admin",
                )
              }
            />
            {current?.snapshot_id && portal === "agency" && (
              <Link
                className="text-primary"
                href={"/admin/creative-studio?brief=" + current.id}
              >
                Open Creative Studio
              </Link>
            )}
            {!!approvals?.length && (
              <details className="rounded-lg border border-border p-4">
                <summary>Approval history</summary>
                {approvals.map((s) => (
                  <article key={s.id} className="mt-3">
                    <strong>
                      Version {s.version} · {s.fields.title}
                    </strong>
                    <p>Approved {s.approved_at.slice(0, 10)}</p>
                    <p>{s.fields.objective}</p>
                    {s.attachments.map((f) => (
                      <p key={f.id}>
                        <a
                          className="text-primary"
                          href={"/api/v1/files/" + f.id + "/download" + suffix}
                        >
                          {f.name}
                        </a>
                      </p>
                    ))}
                  </article>
                ))}
              </details>
            )}
          </div>
        </div>
      ) : (
        <p>No accessible projects.</p>
      )}
    </div>
  );
}
