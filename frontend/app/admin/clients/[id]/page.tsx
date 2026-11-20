import Link from "next/link";
import { redirect, notFound } from "next/navigation";
import { ClientInvite } from "@/components/client-invite";
import { OperationForm } from "@/components/operation-form";
import { getApi, requirePortal } from "@/lib/server-api";
import { canManage, type Project } from "@/lib/projects";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const me = await requirePortal("admin");
  if (!canManage(me.agency_roles)) redirect("/admin/dashboard");
  const id = encodeURIComponent((await params).id),
    path = "/clients/" + id;
  const client = await getApi<{ company_name: string }>(
    path + "?portal=agency",
  );
  if (!client) notFound();
  const [members, projects, invitations] = await Promise.all([
    getApi<{ id: string; name: string; role: string; is_active: boolean }[]>(
      path + "/members",
    ),
    getApi<Project[]>("/projects?portal=agency&client_id=" + id),
    getApi<
      {
        id: string;
        email: string;
        role: string;
        accepted_at: string | null;
        revoked_at: string | null;
        expires_at: string;
      }[]
    >(path + "/invitations"),
  ]);
  return (
    <div className="space-y-6">
      <Link href="/admin/clients">Client directory</Link>
      <h2>{client.company_name}</h2>
      <section>
        <h3>Active projects</h3>
        {projects?.map((p) => (
          <p key={p.id}>
            <Link href={"/admin/projects/" + p.id}>{p.name}</Link>
          </p>
        ))}
        {!projects?.length && <p>No projects yet.</p>}
      </section>
      <section>
        <h3>Client members</h3>
        {members?.map((m) => (
          <p key={m.id}>
            {m.name} · {m.role.replace("_", " ")} ·{" "}
            {m.is_active ? "Active" : "Inactive"}
          </p>
        ))}
        {!members?.length && <p>No members yet.</p>}
      </section>
      <ClientInvite clientId={id} />
      <section>
        <h3>Invitation history</h3>
        <ul>
          {invitations?.map((i) => (
            <li key={i.id} className="border-b border-border py-3">
              <strong>{i.email}</strong> ·{" "}
              {i.accepted_at
                ? "Accepted"
                : i.revoked_at
                  ? "Revoked"
                  : "Expires " + i.expires_at.slice(0, 10)}
              {!i.accepted_at && !i.revoked_at && (
                <OperationForm
                  path={path + "/invitations/" + i.id + "/revoke"}
                  label="Revoke invitation"
                />
              )}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
