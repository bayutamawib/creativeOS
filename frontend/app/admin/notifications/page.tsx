import Link from "next/link";
import { getApi, requirePortal } from "@/lib/server-api";
export default async function Page() {
  await requirePortal("admin");
  const rows = await getApi<
    {
      id: string;
      message: string;
      delivered_at: string;
      resource_type: string;
      brief_id: string | null;
      resource_id: string;
    }[]
  >("/notifications");
  return (
    <>
      <h2>Development inbox</h2>
      <ul className="divide-y divide-border">
        {rows?.map((n) => (
          <li key={n.id} className="py-4">
            <Link
              href={
                n.resource_type === "lead"
                  ? "/admin/leads/" + n.resource_id
                  : n.resource_type === "content_item"
                    ? "/admin/approvals?item=" + n.resource_id
                    : n.resource_type === "task"
                      ? "/admin/tasks"
                      : "/admin/creative-studio?brief=" + n.brief_id
              }
            >
              {n.message}
            </Link>
            <p className="text-sm text-slate-600">
              {new Date(n.delivered_at)
                .toISOString()
                .slice(0, 16)
                .replace("T", " ")}{" "}
              UTC
            </p>
          </li>
        ))}
      </ul>
      {!rows?.length && <p>No notifications yet.</p>}
    </>
  );
}
