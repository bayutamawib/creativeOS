export type DeadlineIndicator = "Overdue" | "Due soon" | "Upcoming" | "Completed";

export function deadlineIndicator(
  status: string,
  due: string | null,
  timezone: string,
  at = new Date(),
): DeadlineIndicator {
  if (status === "completed") return "Completed";
  if (!due) return "Upcoming";
  const today = new Intl.DateTimeFormat("sv-SE", { timeZone: timezone }).format(at);
  const difference = Math.round(
    (Date.parse(`${due}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`)) / 86400000,
  );
  if (difference < 0) return "Overdue";
  if (difference <= 2) return "Due soon";
  return "Upcoming";
}

export function plannedOrder(
  left: { status: string; due: string | null },
  right: { status: string; due: string | null },
) {
  const leftDone = left.status === "completed" ? 1 : 0;
  const rightDone = right.status === "completed" ? 1 : 0;
  return (
    leftDone - rightDone ||
    (left.due ?? "9999-12-31").localeCompare(right.due ?? "9999-12-31")
  );
}
