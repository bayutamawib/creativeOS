import { describe, expect, test } from "vitest";
import { taskPageHref, taskViewHref, type TaskQuery } from "../lib/task-filters";
import {
  allowedTaskStatuses,
  isTaskStatus,
  TASK_STATUSES,
  TASK_STATUS_LABELS,
} from "../lib/task-statuses";

describe("task status contract", () => {
  test("is a runtime array matching every supported backend task status", () => {
    expect(Array.isArray(TASK_STATUSES)).toBe(true);
    expect(TASK_STATUSES.map((status) => status)).toEqual([
      "todo",
      "in_progress",
      "in_review",
      "completed",
      "blocked",
      "cancelled",
    ]);
    expect(Object.keys(TASK_STATUS_LABELS).sort()).toEqual([...TASK_STATUSES].sort());
    expect(isTaskStatus("in_review")).toBe(true);
    expect(isTaskStatus("invented_status")).toBe(false);
  });

  test("preserves the existing role-aware transition choices", () => {
    expect(allowedTaskStatuses("in_progress", false)).not.toContain("cancelled");
    expect(allowedTaskStatuses("in_progress", true)).toContain("cancelled");
    expect(allowedTaskStatuses("completed", false)).toEqual(["completed"]);
    expect(allowedTaskStatuses("completed", true)).toEqual(["completed", "todo"]);
  });
});

test("board, table, and pagination links preserve active task filters", () => {
  const query: TaskQuery = {
    project_id: "project-1",
    status: "in_progress",
    priority: "urgent",
    assignee_id: "member-1",
    due_from: "2026-11-01",
    due_to: "2026-11-30",
    overdue: "true",
    page: "2",
  };
  const board = new URLSearchParams(taskViewHref(query, "board").slice(1));
  const table = new URLSearchParams(taskViewHref(query, "table").slice(1));
  const next = new URLSearchParams(taskPageHref(query, 3, "table").slice(1));

  for (const key of [
    "project_id",
    "status",
    "priority",
    "assignee_id",
    "due_from",
    "due_to",
    "overdue",
  ]) {
    expect(board.get(key)).toBe(query[key as keyof TaskQuery]);
    expect(table.get(key)).toBe(query[key as keyof TaskQuery]);
    expect(next.get(key)).toBe(query[key as keyof TaskQuery]);
  }
  expect(board.get("view")).toBe("board");
  expect(table.get("view")).toBe("table");
  expect(next.get("view")).toBe("table");
  expect(next.get("page")).toBe("3");
});
