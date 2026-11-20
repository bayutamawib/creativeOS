import { requirePortal, getApi } from "@/lib/server-api";
import { AgencyMembers, type Member } from "@/components/agency-members";
export default async function Dashboard() {
  const me = await requirePortal("admin");
  const manage =
    me.agency_roles.includes("admin") ||
    me.agency_roles.includes("agency_manager");
  if (manage) {
    const [members, settings] = await Promise.all([
      getApi<Member[]>("/agency/members"),
      getApi<{ timezone: string }>("/agency/settings/operations"),
    ]);
    return (
      <AgencyMembers
        members={members ?? []}
        timezone={settings?.timezone ?? ""}
        admin={me.agency_roles.includes("admin")}
      />
    );
  }
  return (
    <>
      <h2 className="text-xl font-semibold">Agency membership</h2>
      <p className="mt-3 text-slate-600">{me.email} · Team Member</p>
    </>
  );
}
