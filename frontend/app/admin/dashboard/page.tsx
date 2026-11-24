import { requirePortal, getApi } from "@/lib/server-api";
import { AgencyMembers, type Member } from "@/components/agency-members";
import {
  AgencyOperationsDashboard,
  type AgencyDashboardData,
} from "@/components/operations-dashboard";
export default async function Dashboard() {
  const me = await requirePortal("admin");
  const manage =
    me.agency_roles.includes("admin") ||
    me.agency_roles.includes("agency_manager");
  const [operations, members, settings] = await Promise.all([
    getApi<AgencyDashboardData>("/dashboard/agency"),
    manage ? getApi<Member[]>("/agency/members") : null,
    manage ? getApi<{ timezone: string }>("/agency/settings/operations") : null,
  ]);
  return (
    <div className="space-y-10">
      {operations && <AgencyOperationsDashboard data={operations} />}
      {manage ? (
      <AgencyMembers
        members={members ?? []}
        timezone={settings?.timezone ?? ""}
        admin={me.agency_roles.includes("admin")}
      />
      ) : (
        <section>
          <h2 className="text-xl font-semibold">Agency membership</h2>
          <p className="mt-3 text-slate-600">{me.email} · Team Member</p>
        </section>
      )}
    </div>
  );
}
