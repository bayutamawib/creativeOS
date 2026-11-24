import Link from "next/link";
import { TaskWorkspace } from "@/components/task-workspace";
import { Button, buttonVariants } from "@/components/ui/button";
import { canManage, type Project, type Task } from "@/lib/projects";
import { getApi, requirePortal } from "@/lib/server-api";
import {
  taskPageHref,
  taskParams,
  taskViewHref,
  type TaskQuery,
} from "@/lib/task-filters";
import { TASK_STATUSES } from "@/lib/task-statuses";

type RosterMember = {
  id: string;
  full_name: string;
  is_active: boolean;
  roles: { role: string; is_active: boolean }[];
};

export default async function Page({ searchParams }: { searchParams: Promise<TaskQuery> }) {
  const query = await searchParams;
  const me = await requirePortal("admin");
  const manager = canManage(me.agency_roles);
  const view = query.view === "table" ? "table" : "board";
  const page = Math.max(1, Number(query.page) || 1);
  const apiParams = taskParams(query, false);
  apiParams.set("page", String(page));
  apiParams.set("page_size", "100");
  const filterKey = taskParams(query).toString() + ":" + view;

  const [tasks, projects, roster] = await Promise.all([
    getApi<Task[]>("/tasks?" + apiParams),
    getApi<Project[]>("/projects?portal=agency&page_size=100"),
    manager ? getApi<RosterMember[]>("/agency/members") : null,
  ]);
  const people = manager
    ? (roster ?? []).filter(
        (member) => member.is_active && member.roles.some((role) => role.is_active),
      )
    : [{ id: me.id, full_name: me.full_name }];

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2>Tasks</h2>
          <p className="mt-1 text-sm text-slate-600">
            Track assigned work and move tasks through the production workflow.
          </p>
        </div>
        <nav aria-label="Task view" className="flex gap-2">
          <Link
            href={taskViewHref(query, "board")}
            aria-current={view === "board" ? "page" : undefined}
            className={buttonVariants({ variant: view === "board" ? "default" : "outline" })}
          >
            Board view
          </Link>
          <Link
            href={taskViewHref(query, "table")}
            aria-current={view === "table" ? "page" : undefined}
            className={buttonVariants({ variant: view === "table" ? "default" : "outline" })}
          >
            Table view
          </Link>
        </nav>
      </header>

      <form
        key={filterKey}
        method="get"
        aria-label="Task filters"
        className="grid items-end gap-3 rounded-xl border border-border bg-white p-4 sm:grid-cols-2 lg:grid-cols-4"
      >
        <input type="hidden" name="view" value={view} />
        <label>
          Project
          <select name="project_id" defaultValue={query.project_id}>
            <option value="">All projects</option>
            {(projects ?? []).map((project) => (
              <option key={project.id} value={project.id}>{project.name}</option>
            ))}
          </select>
        </label>
        <label>
          Status
          <select name="status" defaultValue={query.status}>
            <option value="">All statuses</option>
            {TASK_STATUSES.map((status) => (
              <option key={status} value={status}>{status.replaceAll("_", " ")}</option>
            ))}
          </select>
        </label>
        <label>
          Priority
          <select name="priority" defaultValue={query.priority}>
            <option value="">All priorities</option>
            {(["low", "medium", "high", "urgent"] as const).map((priority) => (
              <option key={priority} value={priority}>{priority}</option>
            ))}
          </select>
        </label>
        <label>
          Assignee
          <select name="assignee_id" defaultValue={query.assignee_id}>
            <option value="">All visible assignees</option>
            {people.map((person) => (
              <option key={person.id} value={person.id}>{person.full_name}</option>
            ))}
          </select>
        </label>
        <label>
          Due from
          <input type="date" name="due_from" defaultValue={query.due_from} />
        </label>
        <label>
          Due through
          <input type="date" name="due_to" defaultValue={query.due_to} />
        </label>
        <label>
          Deadline status
          <select name="overdue" defaultValue={query.overdue}>
            <option value="">All deadlines</option>
            <option value="true">Overdue only</option>
            <option value="false">Not overdue</option>
          </select>
        </label>
        <div className="flex flex-wrap gap-2">
          <Button>Apply filters</Button>
          <Link href={"?view=" + view} className={buttonVariants({ variant: "outline" })}>
            Reset filters
          </Link>
        </div>
      </form>

      <TaskWorkspace initialTasks={tasks ?? []} view={view} manager={manager} />

      <nav aria-label="Task pages" className="flex gap-4">
        {page > 1 && (
          <Link href={taskPageHref(query, page - 1, view)}>Previous page</Link>
        )}
        {(tasks?.length ?? 0) === 100 && (
          <Link href={taskPageHref(query, page + 1, view)}>Next page</Link>
        )}
      </nav>
    </div>
  );
}
