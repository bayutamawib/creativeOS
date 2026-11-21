import "server-only";
import { readApi } from "./read-api";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export type Membership = {
  id: string;
  client_id: string;
  role: string;
  company_name: string;
};
export type Identity = {
  id: string;
  email: string;
  full_name: string;
  agency_roles: string[];
  client_memberships: Membership[];
};

export async function getApi<T>(path: string): Promise<T | null> {
  const jar = await cookies();
  const session = jar.get("__Host-creative_session");
  if (!session) return null;
  const base = process.env.INTERNAL_API_URL ?? "http://backend:8000";
  return readApi(
    base + "/api/v1" + path,
    session.name + "=" + session.value,
    async (res) => {
      if (res.status === 401 || res.status === 404) return null;
      if (!res.ok) throw new Error("Workspace request failed");
      return (await res.json()).data as T;
    },
  );
}
export async function requirePortal(kind: "admin" | "client") {
  const me = await getApi<Identity>("/auth/me");
  if (!me) redirect("/login");
  if (kind === "admin" && !me.agency_roles.length)
    redirect(me.client_memberships.length ? "/client/dashboard" : "/access");
  if (kind === "client" && !me.client_memberships.length)
    redirect(me.agency_roles.length ? "/admin/dashboard" : "/access");
  return me;
}
