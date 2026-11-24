import { Connection } from "@/components/connection";
import Link from "next/link";
import type { ReactNode } from "react";
import { SessionActions } from "@/components/session-actions";
import type { Identity } from "@/lib/server-api";

export function Workspace({
  title,
  me,
  children,
}: {
  title: string;
  me: Identity;
  children: ReactNode;
}) {
  return (
    <main className="w-full min-w-0 px-4 py-6 sm:px-6 sm:py-10 lg:px-8">
      <a
        className="sr-only focus:not-sr-only focus:inline-block"
        href="#workspace-content"
      >
        Skip to content
      </a>
      <div className="flex flex-wrap items-start justify-between gap-5 border-b border-border pb-7">
        <div>
          <p className="mb-2 text-sm text-slate-600">{me.full_name}</p>
          <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
        </div>
        <SessionActions />
      </div>
      {me.agency_roles.length > 0 && me.client_memberships.length > 0 && (
        <nav
          aria-label="Switch portal"
          className="mt-4 flex gap-4 text-sm text-primary"
        >
          <Link href="/admin/dashboard">Agency portal</Link>
          <Link href="/client/dashboard">Client portal</Link>
        </nav>
      )}
      <section className="mt-7 min-w-0 max-w-full rounded-xl border border-border bg-white p-4 sm:p-6">
        {children}
      </section>
      <footer className="mt-5 text-xs text-slate-500">
        <Connection />
      </footer>
    </main>
  );
}
