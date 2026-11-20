import {
  ListFilters,
  listParams,
  type ListQuery,
} from "@/components/list-filters";
import Link from "next/link";
import { getApi, requirePortal } from "@/lib/server-api";
import { redirect } from "next/navigation";
import type { Lead } from "@/lib/intake";
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<ListQuery>;
}) {
  const me = await requirePortal("admin");
  if (!me.agency_roles.some((r) => r === "admin" || r === "agency_manager"))
    redirect("/admin/dashboard");
  const query = await searchParams,
    filters = listParams(query).toString();
  const page = Math.max(1, Number(query.page) || 1);
  const leads = await getApi<Lead[]>("/leads?page=" + page + "&" + filters);
  return (
    <>
      <h2>Lead pipeline</h2>
      <ListFilters
        label="Find leads"
        query={query}
        statuses={[
          "new",
          "contacted",
          "qualified",
          "proposal_sent",
          "converted",
          "rejected",
        ]}
      />
      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr>
              <th>Company</th>
              <th>Contact</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {leads?.map((l) => (
              <tr key={l.id} className="border-t border-border">
                <td className="py-3">
                  <Link className="font-medium" href={"/admin/leads/" + l.id}>
                    {l.company_name}
                  </Link>
                </td>
                <td>{l.contact_name}</td>
                <td>{l.status.replace("_", " ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!leads?.length && <p>No inquiries on this page.</p>}
      <nav className="flex gap-4">
        {page > 1 && (
          <Link href={"?" + filters + "&page=" + (page - 1)}>Previous</Link>
        )}
        {leads?.length === 50 && (
          <Link href={"?" + filters + "&page=" + (page + 1)}>Next</Link>
        )}
      </nav>
    </>
  );
}
