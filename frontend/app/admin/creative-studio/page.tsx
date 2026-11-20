import Link from "next/link";
import { notFound } from "next/navigation";
import { getApi, requirePortal } from "@/lib/server-api";
import { canManage } from "@/lib/projects";
import type { Brief } from "@/lib/briefs";
import type { Studio } from "@/lib/studio";
import { CreativeStudio } from "@/components/creative-studio";
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ brief?: string; page?: string }>;
}) {
  const me = await requirePortal("admin"),
    q = await searchParams,
    page = Math.max(1, Number(q.page) || 1);
  const briefs =
    (await getApi<Brief[]>("/briefs?portal=agency&page=" + page)) || [];
  const id =
      q.brief ||
      briefs.find((b) => b.status === "approved")?.id ||
      briefs[0]?.id,
    data = id
      ? await getApi<Studio>("/briefs/" + encodeURIComponent(id) + "/studio")
      : null;
  if (q.brief && !data) notFound();
  return (
    <div className="space-y-5">
      <h2>Creative Studio</h2>
      <form className="flex flex-wrap items-end gap-3">
        <label>
          Creative brief
          <select name="brief" defaultValue={id}>
            {data && !briefs.some((b) => b.id === id) && (
              <option value={id}>{data.brief.title}</option>
            )}
            {briefs.map((b) => (
              <option key={b.id} value={b.id}>
                {b.title} · {b.status}
              </option>
            ))}
          </select>
        </label>
        <button className="text-primary">Open studio</button>
      </form>
      <nav className="flex gap-3">
        {page > 1 && <Link href={"?page=" + (page - 1)}>Previous briefs</Link>}
        {briefs.length === 50 && (
          <Link href={"?page=" + (page + 1)}>More briefs</Link>
        )}
      </nav>
      {data ? (
        <CreativeStudio
          key={id}
          initial={data}
          manager={canManage(me.agency_roles)}
        />
      ) : (
        <p>Create and approve a brief to begin.</p>
      )}
    </div>
  );
}
