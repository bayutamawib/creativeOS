import Link from "next/link";
import type { Project } from "@/lib/projects";
export function ProjectList({
  rows,
  clientId,
  filters,
  portal,
  page,
}: {
  rows: Project[];
  clientId?: string;
  filters?: string;
  portal: "admin" | "client";
  page: number;
}) {
  const query = clientId
    ? "?client=" + clientId + "&page="
    : filters
      ? "?" + filters + "&page="
      : "?page=";
  return (
    <>
      <ul className="divide-y divide-border">
        {rows.map((row) => (
          <li
            key={row.id}
            className="flex flex-wrap items-center justify-between gap-2 py-4"
          >
            <div>
              <Link href={"/" + portal + "/projects/" + row.id}>
                {row.name}
              </Link>
              <p className="text-sm text-slate-600">
                {row.service_type && row.service_type + " · "}
                {row.progress?.percent ?? 0}% complete
                {row.next_milestone &&
                  " · Next milestone: " + row.next_milestone}
              </p>
            </div>
            <span>
              {row.status.replaceAll("_", " ")} ·{" "}
              {row.due_date || "No deadline"}
            </span>
          </li>
        ))}
      </ul>
      {!rows.length && <p>No projects on this page.</p>}
      <nav className="flex gap-4">
        {page > 1 && <Link href={query + (page - 1)}>Previous page</Link>}
        {rows.length === 50 && <Link href={query + (page + 1)}>Next page</Link>}
      </nav>
    </>
  );
}
