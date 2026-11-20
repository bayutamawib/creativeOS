import { redirect } from "next/navigation";
import { getApi, type Identity } from "@/lib/server-api";
export default async function Home() {
  const me = await getApi<Identity>("/auth/me");
  if (!me) redirect("/login");
  if (me.agency_roles.length) redirect("/admin/dashboard");
  if (me.client_memberships.length) redirect("/client/dashboard");
  redirect("/access");
}
