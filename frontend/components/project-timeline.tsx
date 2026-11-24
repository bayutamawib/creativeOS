import Link from "next/link";
import { OperationForm } from "@/components/operation-form";
import { ProjectActivityTimeline, type ProjectActivityPage } from "@/components/project-activity";
import { MilestoneFields, TaskCard, TaskFields } from "@/components/project-controls";
import {
  TaskTemplateApplication,
  type TaskTemplate,
} from "@/components/task-template-application";
import type { Milestone, Person, Project, Task } from "@/lib/projects";
import { deadlineIndicator, plannedOrder } from "@/lib/project-timeline";

type PlannedItem = {
  id: string;
  kind: "Task" | "Milestone";
  title: string;
  description: string | null;
  due: string | null;
  status: string;
  assignees: string[];
  task?: Task;
  milestone?: Milestone;
};

export function ProjectTimeline({
  project,
  tasks,
  milestones,
  members,
  activity,
  templates = [],
  manager,
  portal,
  tab,
  mediaPage,
}: {
  project: Project;
  tasks: Task[];
  milestones: Milestone[];
  members: Person[];
  activity: ProjectActivityPage;
  templates?: TaskTemplate[];
  manager: boolean;
  portal: "agency" | "client";
  tab: "upcoming" | "history";
  mediaPage?: string;
}) {
  const planned: PlannedItem[] = [
    ...tasks
      .filter((task) => task.status !== "cancelled")
      .map((task) => ({
        id: task.id,
        kind: "Task" as const,
        title: task.title,
        description: task.description,
        due: task.due_date,
        status: task.status,
        assignees: task.assignee_names,
        task,
      })),
    ...milestones.map((milestone) => ({
      id: milestone.id,
      kind: "Milestone" as const,
      title: milestone.name,
      description: milestone.description ?? null,
      due: milestone.due_date,
      status: milestone.status,
      assignees: [],
      milestone,
    })),
  ].sort(plannedOrder);
  const base = portal === "agency" ? `/admin/projects/${project.id}` : `/client/projects/${project.id}`;
  return (
    <section aria-labelledby="project-timeline-title" className="space-y-5">
      <div>
        <h3 id="project-timeline-title">Project timeline</h3>
        <p className="mt-1 text-sm text-slate-600">Plan upcoming work and review immutable project history.</p>
      </div>
      <nav aria-label="Project timeline views" className="flex gap-2 border-b border-border pb-3">
        <Link className="rounded-md px-3 py-2 aria-[current=page]:bg-accent" aria-current={tab === "upcoming" ? "page" : undefined} href={`${base}?timeline=upcoming#project-timeline-title`}>Upcoming</Link>
        <Link className="rounded-md px-3 py-2 aria-[current=page]:bg-accent" aria-current={tab === "history" ? "page" : undefined} href={`${base}?timeline=history#project-timeline-title`}>History</Link>
      </nav>
      {tab === "history" ? (
        <ProjectActivityTimeline activity={activity} mediaPage={mediaPage} />
      ) : (
        <div className="space-y-5">
          {manager && (
            <div className="grid gap-4 lg:grid-cols-3">
              <details className="rounded-lg border border-border p-4">
                <summary>Add planned task</summary>
                <OperationForm path={`/projects/${project.id}/tasks`} label="Create planned task">
                  <TaskFields stages={milestones} />
                </OperationForm>
              </details>
              <TaskTemplateApplication project={project.id} templates={templates} defaultStart={project.start_date} />
              <details className="rounded-lg border border-border p-4">
                <summary>Add milestone</summary>
                <OperationForm path={`/projects/${project.id}/milestones`} label="Create milestone">
                  <MilestoneFields />
                </OperationForm>
              </details>
            </div>
          )}
          {!planned.length && (
            <p className="rounded-lg border border-dashed border-border p-6 text-sm text-slate-600">
              No planned work yet. Add a task or milestone to build the project plan.
            </p>
          )}
          <ol className="space-y-4">
            {planned.map((item) => {
              const indicator = deadlineIndicator(
                item.status,
                item.due,
                activity.timezone,
              );
              return (
                <li key={`${item.kind}-${item.id}`} className="rounded-xl border border-border bg-white p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{item.kind}</p>
                      <p className="font-semibold [overflow-wrap:anywhere]">{item.title}</p>
                    </div>
                    <span className={`shrink-0 rounded-full px-2 py-1 text-xs font-semibold ${indicator === "Overdue" ? "bg-red-100 text-red-800" : indicator === "Due soon" ? "bg-amber-100 text-amber-900" : indicator === "Completed" ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-700"}`}>{indicator}</span>
                  </div>
                  {item.description && <p className="mt-2 text-sm text-slate-700">{item.description}</p>}
                  <p className="mt-2 text-sm text-slate-600">Due: {item.due ?? "No deadline"} · Status: {item.status.replaceAll("_", " ")}</p>
                  {!!item.assignees.length && <p className="text-sm text-slate-600">Assigned: {item.assignees.join(", ")}</p>}
                  {portal === "agency" && item.task && (
                    <div className="mt-4"><TaskCard task={item.task} manager={manager} members={members} stages={milestones} /></div>
                  )}
                  {manager && item.milestone && (
                    <details className="mt-3"><summary>Edit milestone</summary><OperationForm path={`/milestones/${item.id}`} method="PATCH" label="Save milestone"><MilestoneFields stage={item.milestone} /></OperationForm></details>
                  )}
                </li>
              );
            })}
          </ol>
        </div>
      )}
    </section>
  );
}
