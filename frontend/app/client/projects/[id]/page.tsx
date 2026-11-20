import Link from "next/link";
import { notFound } from "next/navigation";
import { getApi, requirePortal } from "@/lib/server-api";
import type { Milestone, Progress, Project } from "@/lib/projects";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requirePortal("client");
  const path = "/projects/" + encodeURIComponent((await params).id);
  const p = await getApi<Project>(path + "?portal=client");
  if (!p) notFound();
  const [milestones, progress] = await Promise.all([
    getApi<Milestone[]>(path + "/milestones?portal=client"),
    getApi<Progress>(path + "/progress?portal=client"),
  ]);
  return (
    <div className="space-y-5">
      <Link href={"/client/projects?client=" + p.client_id}>All projects</Link>
      <h2>{p.name}</h2>
      <p>
        {p.status.replaceAll("_", " ")} · {p.due_date || "No target date"}
      </p>
      <h3>Milestone progress</h3>
      <progress
        value={progress?.percent || 0}
        max={100}
        aria-label="Milestone progress"
      />
      <p>
        {progress?.completed_milestones} of {progress?.total_milestones}{" "}
        complete · {progress?.percent}%
      </p>
      <ul className="divide-y divide-border">
        {milestones?.map((s) => (
          <li key={s.id} className="py-3">
            <strong>{s.name}</strong>
            <p>
              {s.status.replaceAll("_", " ")} · {s.due_date || "No date set"}
            </p>
          </li>
        ))}
      </ul>
      {!milestones?.length && <p>No milestones have been shared yet.</p>}
    </div>
  );
}
