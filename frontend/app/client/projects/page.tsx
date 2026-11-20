import Link from "next/link";
import { getApi, requirePortal } from "@/lib/server-api";
import { ProjectList } from "@/components/project-list";
import type { Project } from "@/lib/projects";
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ page?: string; client?: string }>;
}) {
  const me = await requirePortal("client");
  const query = await searchParams;
  const selected =
    me.client_memberships.find((m) => m.client_id === query.client) ??
    me.client_memberships[0];

  const page = Math.max(1, Number(query.page) || 1),
    rows = await getApi<Project[]>(
      "/projects?portal=client&client_id=" +
        selected.client_id +
        "&page=" +
        page,
    );
  return (
    <>
      <h2>Your projects</h2>
      {me.client_memberships.length > 1 && (
        <nav
          aria-label="Client organizations"
          className="my-4 flex flex-wrap gap-3"
        >
          {me.client_memberships.map((m) => (
            <Link
              key={m.id}
              aria-current={selected.id === m.id ? "page" : undefined}
              href={"?client=" + m.client_id}
            >
              {m.company_name}
            </Link>
          ))}
        </nav>
      )}
      <ProjectList
        clientId={selected.client_id}
        rows={rows || []}
        portal="client"
        page={page}
      />
    </>
  );
}
