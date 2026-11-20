import Link from "next/link";
import type { ReactNode } from "react";
import { Workspace } from "@/components/workspace";
import { requirePortal } from "@/lib/server-api";
export default async function Layout({ children }: { children: ReactNode }) {
  const me = await requirePortal("admin");
  return (
    <Workspace me={me} title="Agency workspace">
      <nav
        aria-label="Agency navigation"
        className="mb-6 flex flex-wrap gap-5 border-b border-border pb-4"
      >
        <Link href="/admin/dashboard">Overview</Link>
        <Link href="/admin/projects">Projects</Link>
        <Link href="/admin/briefs">Briefs</Link>
        <Link href="/admin/reports">Reports</Link>
        <Link href="/admin/approvals">Approvals</Link>
        <Link href="/admin/creative-studio">Creative Studio</Link>
        <Link href="/admin/tasks">Tasks</Link>
        <Link href="/admin/notifications">Inbox</Link>
        {me.agency_roles.some(
          (r) => r === "admin" || r === "agency_manager",
        ) && (
          <>
            <Link href="/admin/leads">Leads</Link>
            <Link href="/admin/automation">Automation</Link>
            <Link href="/admin/evaluations">AI evaluations</Link>
            <Link href="/admin/clients">Clients</Link>
          </>
        )}
      </nav>
      {children}
    </Workspace>
  );
}
