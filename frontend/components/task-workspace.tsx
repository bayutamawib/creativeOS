"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type DragEvent } from "react";
import { mutate } from "@/lib/browser-api";
import type { Task } from "@/lib/projects";
import {
  allowedTaskStatuses,
  isTaskStatus,
  TASK_STATUSES,
  TASK_STATUS_LABELS,
  type TaskStatus,
} from "@/lib/task-statuses";

function Priority({ value }: { value: string }) {
  const style =
    value === "urgent"
      ? "bg-red-100 text-red-800"
      : value === "high"
        ? "bg-amber-100 text-amber-900"
        : "bg-slate-100 text-slate-700";
  return (
    <span className={"rounded-full px-2 py-1 text-xs font-medium " + style}>
      {value}
    </span>
  );
}

function TaskCard({
  task,
  manager,
  busy,
  move,
}: {
  task: Task;
  manager: boolean;
  busy: boolean;
  move: (task: Task, status: TaskStatus) => Promise<void>;
}) {
  return (
    <article
      draggable={!busy && allowedTaskStatuses(task.status, manager).length > 1}
      onDragStart={(event) => {
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/task-id", task.id);
      }}
      className={
        "space-y-4 rounded-xl border bg-white p-4 shadow-sm transition-shadow hover:shadow-md " +
        (task.is_overdue ? "border-red-400" : "border-border")
      }
      aria-busy={busy}
    >
      <div className="flex items-start justify-between gap-3">
        <h4 className="min-w-0 text-base font-semibold leading-6 [overflow-wrap:anywhere]">
          <Link
            className="text-primary"
            href={"/admin/projects/" + task.project_id + "#task-" + task.id}
          >
            {task.title}
          </Link>
        </h4>
        <span className="shrink-0"><Priority value={task.priority} /></span>
      </div>
      <p className="text-sm text-slate-600">{task.project_name}</p>
      <p className="text-sm">{task.assignee_names.join(", ") || "Unassigned"}</p>
      <p className={task.is_overdue ? "text-sm font-semibold text-red-700" : "text-sm"}>
        {task.is_overdue ? "Overdue · " : ""}
        {task.due_date || "No deadline"}
      </p>
      <label className="text-sm">
        Move task
        <select
          aria-label={"Move " + task.title}
          value={task.status}
          disabled={busy || allowedTaskStatuses(task.status, manager).length === 1}
          onChange={(event) => {
            if (isTaskStatus(event.target.value)) void move(task, event.target.value);
          }}
        >
          {allowedTaskStatuses(task.status, manager).map((status) => (
            <option key={status} value={status}>
              {TASK_STATUS_LABELS[status]}
            </option>
          ))}
        </select>
      </label>
    </article>
  );
}

export function TaskWorkspace({
  initialTasks,
  view,
  manager,
}: {
  initialTasks: Task[];
  view: "board" | "table";
  manager: boolean;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const router = useRouter();

  async function move(task: Task, status: TaskStatus) {
    if (status === task.status || busy) return;
    setBusy(task.id);
    setMessage("");
    try {
      await mutate("/tasks/" + task.id, "PATCH", {
        status,
        expected_updated_at: task.updated_at,
      });
      setMessage(task.title + " moved to " + TASK_STATUS_LABELS[status]);
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Task could not be moved");
    } finally {
      setBusy(null);
    }
  }

  function drop(event: DragEvent<HTMLElement>, status: TaskStatus) {
    event.preventDefault();
    const task = initialTasks.find(
      (row) => row.id === event.dataTransfer.getData("text/task-id"),
    );
    if (task && allowedTaskStatuses(task.status, manager).includes(status)) {
      void move(task, status);
    }
  }

  return (
    <section aria-label="Task results" className="space-y-4">
      <p role="status" aria-live="polite" className="min-h-5 text-sm">
        {message}
      </p>
      {!initialTasks.length && (
        <div className="rounded-lg border border-dashed border-border p-8 text-center">
          <h3>No tasks match these filters</h3>
          <p className="mt-2 text-sm text-slate-600">Reset or adjust the filters to see tasks.</p>
        </div>
      )}
      {view === "board" && initialTasks.length > 0 && (
        <div
          className="grid max-w-full snap-x grid-flow-col auto-cols-[18rem] items-start gap-4 overflow-x-auto overscroll-x-contain pb-4 lg:auto-cols-[20rem]"
          aria-label="Kanban columns"
        >
          {TASK_STATUSES.map((status) => {
            const columnTasks = initialTasks.filter((task) => task.status === status);
            return (
              <section
                key={status}
                aria-labelledby={"column-" + status}
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => drop(event, status)}
                className="min-h-48 snap-start space-y-3 rounded-xl bg-slate-100 p-3"
              >
                <header className="flex items-center justify-between gap-2">
                  <h3 id={"column-" + status}>{TASK_STATUS_LABELS[status]}</h3>
                  <span className="rounded-full bg-white px-2 py-1 text-xs" aria-label={columnTasks.length + " tasks"}>
                    {columnTasks.length}
                  </span>
                </header>
                {columnTasks.map((task) => (
                  <TaskCard key={task.id} task={task} manager={manager} busy={busy === task.id} move={move} />
                ))}
                {!columnTasks.length && (
                  <p className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-500">No tasks</p>
                )}
              </section>
            );
          })}
        </div>
      )}
      {view === "table" && initialTasks.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-border bg-white">
          <table className="w-full text-left">
            <thead className="bg-slate-100">
              <tr>
                {["Task", "Project", "Assignees", "Priority", "Status", "Deadline"].map((heading) => (
                  <th scope="col" key={heading} className="px-3 py-3">{heading}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {initialTasks.map((task) => (
                <tr key={task.id} className="border-t border-border">
                  <th scope="row" className="px-3 py-3 font-medium">
                    <Link className="text-primary" href={"/admin/projects/" + task.project_id + "#task-" + task.id}>{task.title}</Link>
                  </th>
                  <td className="px-3 py-3">{task.project_name}</td>
                  <td className="px-3 py-3">{task.assignee_names.join(", ") || "Unassigned"}</td>
                  <td className="px-3 py-3"><Priority value={task.priority} /></td>
                  <td className="min-w-44 px-3 py-3">
                    <select
                      aria-label={"Move " + task.title}
                      value={task.status}
                      disabled={
                        busy === task.id ||
                        allowedTaskStatuses(task.status, manager).length === 1
                      }
                      onChange={(event) => {
                        if (isTaskStatus(event.target.value)) {
                          void move(task, event.target.value);
                        }
                      }}
                    >
                      {allowedTaskStatuses(task.status, manager).map((status) => (
                        <option key={status} value={status}>{TASK_STATUS_LABELS[status]}</option>
                      ))}
                    </select>
                  </td>
                  <td className={"px-3 py-3 " + (task.is_overdue ? "font-semibold text-red-700" : "")}>
                    {task.is_overdue ? "Overdue · " : ""}{task.due_date || "No deadline"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
