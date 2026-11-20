import Link from "next/link";
import { getApi, requirePortal } from "@/lib/server-api";
export default async function Page() {
  await requirePortal("client");
  const rows = await getApi<
    {
      id: string;
      resource_id: string;
      resource_type: string;
      message: string;
      delivered_at: string;
    }[]
  >("/notifications?portal=client");
  return (
    <section>
      <h2>Client inbox</h2>
      <ul className="divide-y divide-border">
        {rows?.map((n) => (
          <li className="py-4" key={n.id}>
            <Link
              href={
                (n.resource_type === "report"
                  ? "/client/reports/"
                  : "/client/approvals?item=") + n.resource_id
              }
            >
              {n.message}
            </Link>
            <p className="text-xs">
              {n.delivered_at.slice(0, 16).replace("T", " ")} UTC
            </p>
          </li>
        ))}
      </ul>
      {!rows?.length && <p>No notifications yet.</p>}
    </section>
  );
}
