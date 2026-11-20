import Link from "next/link";
import type { ReactNode } from "react";
import { Workspace } from "@/components/workspace";
import { requirePortal } from "@/lib/server-api";
export default async function Layout({ children }: { children: ReactNode }) {
  const me = await requirePortal("client");
  return (
    <Workspace me={me} title="Client workspace">
      <nav
        aria-label="Client navigation"
        className="mb-6 flex gap-4 border-b border-border pb-4"
      >
        <Link href="/client/dashboard">Overview</Link>
        <Link href="/client/projects">Projects</Link>
      </nav>
      {children}
    </Workspace>
  );
}
