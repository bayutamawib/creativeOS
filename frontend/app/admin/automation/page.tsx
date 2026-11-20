import { notFound } from "next/navigation";
import { getApi, requirePortal } from "@/lib/server-api";
export default async function Page() {
  const me = await requirePortal("admin");
  if (!me.agency_roles.some((r) => r === "admin" || r === "agency_manager"))
    notFound();
  const rows =
    await getApi<
      {
        event_id: string;
        event_type: string;
        delivery: string;
        attempt: number;
        status: string | null;
        execution: string | null;
        error: string | null;
      }[]
    >("/automation/runs");
  return (
    <section>
      <h2>Automation activity</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr>
              {["Event", "Delivery", "Attempt", "n8n execution", "Outcome"].map(
                (c) => (
                  <th key={c} className="py-2">
                    {c}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {rows?.map((r) => (
              <tr key={r.event_id} className="border-t border-border">
                <td className="py-2">{r.event_type}</td>
                <td>{r.delivery}</td>
                <td>{r.attempt}</td>
                <td>{r.execution || "—"}</td>
                <td>{r.error || r.status || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
