import Link from "next/link";
import { getApi, requirePortal } from "@/lib/server-api";
import type { Task } from "@/lib/projects";
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>;
}) {
  await requirePortal("admin");
  const page = Math.max(1, Number((await searchParams).page) || 1);
  const rows = await getApi<Task[]>("/tasks?page=" + page);
  return (
    <>
      <h2>Task schedule</h2>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr>
              {[
                "Task",
                "Project",
                "Assignees",
                "Priority",
                "Status",
                "Deadline",
              ].map((h) => (
                <th key={h} className="px-2 py-3">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows?.map((t) => (
              <tr key={t.id} className="border-t border-border">
                <td className="px-2 py-3">
                  <Link
                    className="text-primary"
                    href={"/admin/projects/" + t.project_id}
                  >
                    {t.title}
                  </Link>
                </td>
                <td>{t.project_name}</td>
                <td>{t.assignee_names.join(", ") || "Unassigned"}</td>
                <td>{t.priority}</td>
                <td>{t.status.replaceAll("_", " ")}</td>
                <td>{t.due_date || "No deadline"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!rows?.length && <p>No assigned tasks on this page.</p>}
      <nav className="flex gap-4">
        {page > 1 && <Link href={"?page=" + (page - 1)}>Previous page</Link>}
        {rows?.length === 50 && (
          <Link href={"?page=" + (page + 1)}>Next page</Link>
        )}
      </nav>
    </>
  );
}
