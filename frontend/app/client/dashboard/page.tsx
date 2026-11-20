import Link from "next/link";
import { getApi, requirePortal } from "@/lib/server-api";
import { Delegates, type Delegate } from "@/components/delegates";
type Project = { id: string; name: string };
type Authority = {
  has_binding_authority: boolean;
  can_manage_delegations: boolean;
};
export default async function Dashboard({
  searchParams,
}: {
  searchParams: Promise<{ client?: string; project?: string }>;
}) {
  const me = await requirePortal("client");
  const query = await searchParams;
  const member =
    me.client_memberships.find((m) => m.client_id === query.client) ??
    me.client_memberships[0];
  const projects =
    (await getApi<Project[]>("/clients/" + member.client_id + "/projects")) ??
    [];
  const project = projects.find((p) => p.id === query.project) ?? projects[0];
  const base = project && "/projects/" + project.id;
  const authority = base
    ? await getApi<Authority>(base + "/approval-authority")
    : null;
  const delegates = authority?.can_manage_delegations
    ? await getApi<Delegate[]>(base + "/approval-delegations")
    : null;
  return (
    <div className="space-y-6">
      {me.client_memberships.length > 1 && (
        <nav aria-label="Organizations" className="flex gap-3">
          {me.client_memberships.map((m) => (
            <Link key={m.id} href={"?client=" + m.client_id}>
              {m.company_name}
            </Link>
          ))}
        </nav>
      )}
      <h2 className="text-2xl font-semibold">{member.company_name}</h2>
      <h3 className="text-lg font-medium">Projects</h3>
      {projects.length ? (
        <nav aria-label="Projects" className="flex flex-wrap gap-2">
          {projects.map((p) => (
            <Link
              key={p.id}
              aria-current={p.id === project?.id ? "page" : undefined}
              className="rounded-md border border-border px-3 py-2 text-sm aria-[current=page]:bg-accent"
              href={"?client=" + member.client_id + "&project=" + p.id}
            >
              {p.name}
            </Link>
          ))}
        </nav>
      ) : (
        <p>No projects assigned.</p>
      )}
      {project && (
        <section className="space-y-3 border-t border-border pt-5">
          <h3 className="font-semibold">{project.name}</h3>
          <p className="text-sm text-slate-600">
            Your review access ·{" "}
            {authority?.has_binding_authority
              ? "Approval and revision requests"
              : "View and comment"}
          </p>
          {delegates && (
            <Delegates projectId={project.id} members={delegates} />
          )}
        </section>
      )}
    </div>
  );
}
