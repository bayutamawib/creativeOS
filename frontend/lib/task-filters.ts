export type TaskQuery = {
  view?: string;
  page?: string;
  project_id?: string;
  status?: string;
  priority?: string;
  assignee_id?: string;
  due_from?: string;
  due_to?: string;
  overdue?: string;
};

const FILTER_KEYS = [
  "project_id",
  "status",
  "priority",
  "assignee_id",
  "due_from",
  "due_to",
  "overdue",
] as const;

export function taskParams(query: TaskQuery, includePage = true) {
  const params = new URLSearchParams();
  for (const key of FILTER_KEYS) if (query[key]) params.set(key, query[key]);
  if (includePage && query.page) params.set("page", query.page);
  return params;
}

export function taskViewHref(query: TaskQuery, view: "board" | "table") {
  const params = taskParams(query);
  params.set("view", view);
  return "?" + params;
}

export function taskPageHref(
  query: TaskQuery,
  page: number,
  view: "board" | "table",
) {
  const params = taskParams(query, false);
  params.set("page", String(page));
  params.set("view", view);
  return "?" + params;
}
