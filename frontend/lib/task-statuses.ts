export const TASK_STATUSES = [
  "todo",
  "in_progress",
  "in_review",
  "completed",
  "blocked",
  "cancelled",
] as const;

export type TaskStatus = (typeof TASK_STATUSES)[number];

export const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
  todo: "To do",
  in_progress: "In progress",
  in_review: "In review",
  completed: "Completed",
  blocked: "Blocked",
  cancelled: "Cancelled",
};

export function isTaskStatus(value: string): value is TaskStatus {
  return TASK_STATUSES.some((status) => status === value);
}

export function allowedTaskStatuses(status: TaskStatus, manager: boolean): TaskStatus[] {
  if (status === "completed" || status === "cancelled") {
    return manager ? [status, "todo"] : [status];
  }
  return TASK_STATUSES.filter((candidate) => manager || candidate !== "cancelled");
}
