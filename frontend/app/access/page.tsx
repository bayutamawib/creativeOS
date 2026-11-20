import { redirect } from "next/navigation";
import { getApi, type Identity } from "@/lib/server-api";
import { SessionActions } from "@/components/session-actions";
export default async function Access() {
  const me = await getApi<Identity>("/auth/me");
  if (!me) redirect("/login");
  return (
    <main className="mx-auto max-w-3xl space-y-6 px-6 py-16">
      <h1 className="text-3xl font-semibold">Workspace access</h1>
      <p>
        Your account has no active workspace membership. Contact your agency
        administrator.
      </p>
      <SessionActions />
    </main>
  );
}
