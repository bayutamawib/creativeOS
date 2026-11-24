import type { ReactNode } from "react";
import { Workspace } from "@/components/workspace";
import { WorkspaceNavigation, type WorkspaceLink } from "@/components/workspace-navigation";
import { requirePortal } from "@/lib/server-api";
export default async function Layout({ children }: { children: ReactNode }) {
  const me = await requirePortal("admin");
  const items: WorkspaceLink[] = [
    { href: "/admin/dashboard", label: "Overview" },
    { href: "/admin/projects", label: "Projects" },
    { href: "/admin/briefs", label: "Briefs" },
    { href: "/admin/reports", label: "Reports" },
    { href: "/admin/approvals", label: "Approvals" },
    { href: "/admin/creative-studio", label: "Creative Studio" },
    { href: "/admin/tasks", label: "Tasks" },
    { href: "/admin/notifications", label: "Inbox" },
  ];
  if (me.agency_roles.some((role) => role === "admin" || role === "agency_manager")) {
    items.push(
      { href: "/admin/leads", label: "Leads" },
      { href: "/admin/automation", label: "Automation" },
      { href: "/admin/evaluations", label: "AI evaluations" },
      { href: "/admin/clients", label: "Clients" },
    );
  }
  return (
    <Workspace me={me} title="Agency workspace">
      <WorkspaceNavigation label="Agency navigation" items={items} />
      <div id="workspace-content" tabIndex={-1} className="min-w-0 max-w-full">
        {children}
      </div>
    </Workspace>
  );
}
