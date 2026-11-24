"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export type WorkspaceLink = { href: string; label: string };

function active(pathname: string, href: string) {
  return pathname === href || (!href.endsWith("/dashboard") && pathname.startsWith(href + "/"));
}

function Links({ items }: { items: WorkspaceLink[] }) {
  const pathname = usePathname();
  return (
    <>
      {items.map((item) => {
        const current = active(pathname, item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={current ? "page" : undefined}
            className="shrink-0 rounded-md px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-accent hover:text-primary aria-[current=page]:bg-accent aria-[current=page]:text-primary"
          >
            {item.label}
          </Link>
        );
      })}
    </>
  );
}

export function WorkspaceNavigation({
  label,
  items,
}: {
  label: string;
  items: WorkspaceLink[];
}) {
  return (
    <div className="mb-6 border-b border-border pb-3">
      <nav aria-label={label} className="hidden max-w-full overflow-x-auto sm:flex sm:gap-1">
        <Links items={items} />
      </nav>
      <details className="sm:hidden">
        <summary className="rounded-md border border-border bg-white px-3 py-2">Workspace menu</summary>
        <nav aria-label={label} className="mt-2 grid grid-cols-2 gap-1 rounded-lg bg-slate-50 p-2">
          <Links items={items} />
        </nav>
      </details>
    </div>
  );
}
