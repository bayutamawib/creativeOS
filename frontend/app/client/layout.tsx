import type { ReactNode } from "react";
import { Workspace } from "@/components/workspace";
import { WorkspaceNavigation, type WorkspaceLink } from "@/components/workspace-navigation";
import { requirePortal } from "@/lib/server-api";
export default async function Layout({ children }: { children: ReactNode }) {
  const me = await requirePortal("client");
  const items: WorkspaceLink[] = [
    { href: "/client/dashboard", label: "Overview" },
    { href: "/client/projects", label: "Projects" },
    { href: "/client/briefs", label: "Briefs" },
    { href: "/client/reports", label: "Reports" },
    { href: "/client/approvals", label: "Approvals" },
    { href: "/client/notifications", label: "Inbox" },
    { href: "/client/files", label: "Files" },
  ];
  return (
    <Workspace me={me} title="Client workspace">
      <WorkspaceNavigation label="Client navigation" items={items} />
      <div id="workspace-content" tabIndex={-1} className="min-w-0 max-w-full">
        {children}
      </div>
    </Workspace>
  );
}
