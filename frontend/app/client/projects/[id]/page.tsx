import { ProjectMedia } from "@/components/project-media";
import type { ProjectActivityPage } from "@/components/project-activity";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getApi, requirePortal } from "@/lib/server-api";
import type { Milestone, Progress, Project } from "@/lib/projects";
import { ProjectTimeline } from "@/components/project-timeline";
export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ media_page?: string; activity_page?: string; timeline?: string }>;
}) {
  const query = await searchParams;
  await requirePortal("client");
  const path = "/projects/" + encodeURIComponent((await params).id);
  const p = await getApi<Project>(path + "?portal=client");
  if (!p) notFound();
  const activityPage = Math.max(1, Number(query.activity_page) || 1);
  const [milestones, progress, activity] = await Promise.all([
    getApi<Milestone[]>(path + "/milestones?portal=client"),
    getApi<Progress>(path + "/progress?portal=client"),
    getApi<ProjectActivityPage>(
      path + "/activity?portal=client&page=" + activityPage + "&page_size=20",
    ),
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
      {activity && (
        <ProjectTimeline
          project={p}
          tasks={[]}
          milestones={milestones ?? []}
          members={[]}
          activity={activity}
          manager={false}
          portal="client"
          tab={query.timeline === "history" ? "history" : "upcoming"}
          mediaPage={query.media_page}
        />
      )}
      <ProjectMedia
        project={p.id}
        portal="client"
        page={Math.max(1, Number(query.media_page) || 1)}
      />
    </div>
  );
}
