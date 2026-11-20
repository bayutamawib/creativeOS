import Link from "next/link";
import { redirect, notFound } from "next/navigation";
import { LeadActions } from "@/components/lead-actions";
import { getApi, requirePortal } from "@/lib/server-api";
import type { Lead } from "@/lib/intake";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const me = await requirePortal("admin");
  if (!me.agency_roles.some((r) => r === "admin" || r === "agency_manager"))
    redirect("/admin/dashboard");
  const [lead, staff] = await Promise.all([
    getApi<Lead>("/leads/" + encodeURIComponent((await params).id)),
    getApi<
      {
        id: string;
        full_name: string;
        is_active: boolean;
        roles: { is_active: boolean }[];
      }[]
    >("/agency/members"),
  ]);
  if (!lead) notFound();
  const activity = await getApi<{ action: string; occurred_at: string }[]>(
    "/leads/" + lead.id + "/activity",
  );
  return (
    <div className="space-y-5">
      <Link href="/admin/leads">All leads</Link>
      <h2>{lead.company_name}</h2>
      <p>
        {lead.contact_name} · {lead.email} · {lead.status}
      </p>
      <p>
        {[lead.industry, lead.service_interest, lead.phone]
          .filter(Boolean)
          .join(" · ")}
      </p>
      <p className="whitespace-pre-wrap">{lead.inquiry_message}</p>
      <p>Source · {lead.source.replaceAll("_", " ")}</p>
      <LeadActions
        lead={lead}
        staff={
          staff?.filter(
            (s) => s.is_active && s.roles.some((r) => r.is_active),
          ) || []
        }
      />
      <section>
        <h3>Activity history</h3>
        <p>{lead.created_at.slice(0, 10)} · Inquiry received</p>
        {activity?.map((a, i) => (
          <p key={i}>
            {a.occurred_at.slice(0, 10)} · {a.action.split(".").join(" ")}
          </p>
        ))}
      </section>
    </div>
  );
}
