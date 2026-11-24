import { ProjectMedia } from "@/components/project-media";
import type { ProjectActivityPage } from "@/components/project-activity";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getApi, requirePortal } from "@/lib/server-api";
import {
  canManage,
  type Person,
  type Project,
  type Milestone,
  type Task,
  type Progress,
} from "@/lib/projects";
import {
  ProjectFields,
} from "@/components/project-controls";
import { OperationForm } from "@/components/operation-form";
import { ProjectTimeline } from "@/components/project-timeline";
import type { TaskTemplate } from "@/components/task-template-application";
export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ media_page?: string; activity_page?: string; timeline?: string }>;
}) {
  const query = await searchParams;
  const me = await requirePortal("admin"),
    manager = canManage(me.agency_roles),
    id = encodeURIComponent((await params).id),
    path = "/projects/" + id;
  const project = await getApi<Project>(path + "?portal=agency");
  if (!project) notFound();
  const activityPage = Math.max(1, Number(query.activity_page) || 1);
  const [stages, tasks, members, progress, staff, activity, templates] = await Promise.all([
    getApi<Milestone[]>(path + "/milestones?portal=agency"),
    getApi<Task[]>(path + "/tasks"),
    getApi<Person[]>(path + "/members"),
    getApi<Progress>(path + "/progress?portal=agency"),
    manager
      ? getApi<
          {
            id: string;
            full_name: string;
            is_active: boolean;
            roles: { is_active: boolean }[];
          }[]
        >("/agency/members")
      : null,
    getApi<ProjectActivityPage>(
      path + "/activity?portal=agency&page=" + activityPage + "&page_size=20",
    ),
    manager ? getApi<TaskTemplate[]>("/task-templates") : null,
  ]);
  const available =
    staff?.filter(
      (s) =>
        s.is_active &&
        s.roles.some((r) => r.is_active) &&
        !members?.some((m) => s.id === m.user_id),
    ) || [];
  return (
    <div className="space-y-7">
      <Link href="/admin/projects">All projects</Link>
      <header>
        <h2>{project.name}</h2>
        <p>
          {project.status.replaceAll("_", " ")} ·{" "}
          {project.due_date || "No deadline"}
        </p>
        <p>{project.description}</p>
      </header>
      {manager && (
        <details>
          <summary>Project settings</summary>
          <OperationForm path={path} method="PATCH" label="Save project">
            <ProjectFields project={project} />
          </OperationForm>
          <div className="mt-4">
            <OperationForm
              path={path + "/archive"}
              after="archive"
              label="Archive project"
            />
          </div>
        </details>
      )}
      <section>
        <h3>Project team</h3>
        <ul className="space-y-2">
          {members?.map((m) => (
            <li key={m.user_id}>
              {manager ? (
                <OperationForm
                  path={path + "/members/" + m.user_id}
                  method="DELETE"
                  label={"Remove " + m.full_name}
                />
              ) : (
                m.full_name
              )}
            </li>
          ))}
        </ul>
        {manager && !!available.length && (
          <OperationForm path={path + "/members"} label="Add project member">
            <label>
              Agency member
              <select name="user_id">
                {available.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.full_name}
                  </option>
                ))}
              </select>
            </label>
          </OperationForm>
        )}
      </section>
      <p className="text-sm text-slate-600">
        Milestones: {progress?.completed_milestones} of {progress?.total_milestones} complete · {progress?.percent}%
      </p>
      {activity && (
        <ProjectTimeline
          project={project}
          tasks={tasks ?? []}
          milestones={stages ?? []}
          members={members ?? []}
          activity={activity}
          templates={templates ?? []}
          manager={manager}
          portal="agency"
          tab={query.timeline === "history" ? "history" : "upcoming"}
          mediaPage={query.media_page}
        />
      )}
      <ProjectMedia
        project={project.id}
        portal="agency"
        page={Math.max(1, Number(query.media_page) || 1)}
      />
    </div>
  );
}
