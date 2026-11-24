import Link from "next/link";
import { ProjectThumbnail } from "@/components/media-card";
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
      <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {rows.map((row) => (
          <li
            key={row.id}
            className="min-w-0 overflow-hidden rounded-xl border border-border bg-white shadow-sm"
          >
            <Link
              className="block"
              aria-label={row.name}
              href={"/" + portal + "/projects/" + row.id}
            >
              <ProjectThumbnail
                id={row.cover_file_id}
                video={Boolean(row.cover_video_id)}
                name={row.name}
                portal={portal === "admin" ? "agency" : "client"}
              />
              <div className="space-y-3 p-4">
                {row.client_name && (
                  <p className="text-xs font-medium text-slate-600">
                    {row.client_name}
                  </p>
                )}
                <h3 className="text-lg">{row.name}</h3>
                <p className="text-sm text-slate-600">
                  {row.status.replaceAll("_", " ")} ·{" "}
                  {row.due_date || "No deadline"}
                </p>
                <progress
                  className="h-2 w-full accent-indigo-600"
                  value={row.progress?.percent ?? 0}
                  max={100}
                  aria-label={row.name + " progress"}
                />
                <p className="text-sm">
                  {row.progress?.percent ?? 0}% complete
                </p>
                {row.next_milestone && (
                  <p className="text-sm text-slate-600">
                    Next milestone · {row.next_milestone}
                  </p>
                )}
              </div>
            </Link>
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
