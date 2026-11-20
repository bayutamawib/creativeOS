import Link from "next/link";
import { getApi, requirePortal } from "@/lib/server-api";
import { redirect } from "next/navigation";
export default async function Page() {
  const me = await requirePortal("admin");
  if (!me.agency_roles.some((r) => r === "admin" || r === "agency_manager"))
    redirect("/admin/dashboard");
  const rows =
    await getApi<{ id: string; company_name: string; email: string | null }[]>(
      "/clients",
    );
  return (
    <>
      <h2>Client directory</h2>
      <ul className="divide-y divide-border">
        {rows?.map((c) => (
          <li key={c.id} className="py-4">
            <Link href={"/admin/clients/" + c.id}>{c.company_name}</Link>
            <p>{c.email}</p>
          </li>
        ))}
      </ul>
    </>
  );
}
