import { describe, expect, test } from "vitest";
import { deadlineIndicator, plannedOrder } from "../lib/project-timeline";

describe("project timeline planning", () => {
  const at = new Date("2026-11-23T17:30:00Z");

  test("uses the agency timezone for deadline indicators", () => {
    expect(deadlineIndicator("todo", "2026-11-23", "Asia/Jakarta", at)).toBe("Overdue");
    expect(deadlineIndicator("todo", "2026-11-24", "Asia/Jakarta", at)).toBe("Due soon");
    expect(deadlineIndicator("todo", "2026-11-27", "Asia/Jakarta", at)).toBe("Upcoming");
    expect(deadlineIndicator("completed", "2026-11-20", "Asia/Jakarta", at)).toBe("Completed");
  });

  test("orders open deadlines before completed work", () => {
    const rows = [
      { status: "completed", due: "2026-11-20" },
      { status: "todo", due: null },
      { status: "in_progress", due: "2026-11-25" },
      { status: "todo", due: "2026-11-24" },
    ].sort(plannedOrder);
    expect(rows).toEqual([
      { status: "todo", due: "2026-11-24" },
      { status: "in_progress", due: "2026-11-25" },
      { status: "todo", due: null },
      { status: "completed", due: "2026-11-20" },
    ]);
  });
});
