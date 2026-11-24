import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";

async function login(page: Page, name: string) {
  const email = name + "@example.com";
  await page.goto("/login");
  await page.getByLabel("Email address").fill(email);
  await page
    .getByLabel("Password", { exact: true })
    .fill(JSON.parse(readFileSync("../.local/demo-accounts.json", "utf8"))[email]);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/dashboard/);
}

function verifyWorkflow(kind: string, resource: string) {
  execFileSync("python3", ["../scripts/verify_workflow.py", kind, resource], {
    encoding: "utf8",
  });
}

async function archiveTestProject(page: Page, projectId: string) {
  return page.evaluate(async (id) => {
    const csrf = document.cookie
      .split("; ")
      .find((value) => value.startsWith("__Host-creative_csrf="))
      ?.split("=")[1];
    if (!csrf) return 403;
    const response = await fetch(`/api/v1/projects/${id}/archive`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRF-Token": csrf },
    });
    return response.status;
  }, projectId);
}

test("agency project management, task board, notification and client-safe milestones", async ({
  page,
  browser,
}) => {
  test.setTimeout(180000);
  const deadline = new Date(Date.now() - 2 * 86400000).toISOString().slice(0, 10);
  const suffix = randomUUID();
  const project = "Z Campaign " + suffix;
  const task = "Internal production " + suffix;
  const milestone = "Public launch " + suffix;
  const brief = "Launch requirements " + suffix;
  const planningStart = "2026-12-01";
  let projectId: string | undefined;
  let archived = false;
  let producer: Page | undefined;
  let client: Page | undefined;

  try {
    await login(page, "manager");
    await page.getByRole("link", { name: "Projects", exact: true }).click();
    await page.getByText("Create project", { exact: true }).first().click();
    await page.getByLabel("Client organization").selectOption({ label: "Clover Press" });
    await page.getByLabel("Project name", { exact: true }).fill(project);
    await page.getByLabel("Internal project description").fill("Confidential planning");
    await page.getByRole("button", { name: "Create project", exact: true }).click();
    await expect(page.getByRole("heading", { name: project })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Project timeline" })).toBeVisible();
    await page.getByRole("tab", { name: "History" }).click();
    await expect(page.getByRole("heading", { name: "Activity timeline" })).toBeVisible();
    await expect(page.getByText("Created the project", { exact: true })).toBeVisible();
    await page.getByRole("tab", { name: "Upcoming" }).click();
    const projectPath = new URL(page.url()).pathname;
    projectId = projectPath.split("/").at(-1);
    expect(projectId).toBeTruthy();

    client = await browser.newPage();
    await login(client, "publisher");
    await client.goto(`/client/briefs/new?project=${projectId}`);
    await client.getByLabel("Brief title").fill(brief);
    await client.getByLabel("Campaign objective").fill("Prepare the launch campaign.");
    await client.getByRole("button", { name: "Save draft" }).click();
    await client.getByRole("button", { name: "Submit brief" }).click();
    await expect(client.getByText(/Version 2 · submitted/)).toBeVisible();
    const briefQuery = new URL(client.url()).search;
    await page.goto("/admin/briefs" + briefQuery);
    await page.getByRole("button", { name: "Approve brief" }).click();
    await expect(page.getByText(/Version 3 · approved/)).toBeVisible();
    await page.goto(projectPath);

    await page.getByLabel("Agency member").selectOption({ label: "Producer" });
    await page.getByRole("button", { name: "Add project member" }).click();
    await expect(page.getByRole("button", { name: "Remove Producer" })).toBeVisible();
    await page.getByText("Add milestone", { exact: true }).click();
    await page.getByLabel("Milestone name").fill(milestone);
    await page.getByLabel("Milestone status").selectOption("completed");
    await page.getByLabel("Release milestone to client").check();
    await page.getByRole("button", { name: "Create milestone" }).click();
    await expect(page.getByText(milestone, { exact: true }).first()).toBeVisible();
    await page.getByText("Apply task template", { exact: true }).click();
    await page.getByLabel("Planning start date").fill(planningStart);
    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("button", { name: "Apply template", exact: true }).click();
    await expect(page.getByRole("status").filter({ hasText: "6 planned tasks created" })).toBeVisible();
    await expect(page.getByText("Creative brief approval", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Due: 2026-12-03", { exact: false }).first()).toBeVisible();

    const planningCard = page.getByRole("heading", { name: "Content planning" }).locator("xpath=..");
    await planningCard.getByText("Edit task", { exact: true }).click();
    await planningCard.getByLabel("Internal task details").fill("Updated template task details");
    await planningCard.getByLabel("Task deadline").fill("2026-12-06");
    await planningCard.getByRole("button", { name: "Save task" }).click();
    await expect(planningCard.getByText("Saved", { exact: true })).toBeVisible();

    const removedCard = page.getByRole("heading", { name: "Design production" }).locator("xpath=..");
    page.once("dialog", (dialog) => dialog.accept());
    await removedCard.getByRole("button", { name: "Remove from plan" }).click();
    await expect(page.getByRole("heading", { name: "Design production" })).toHaveCount(0);

    const reviewCard = page.getByRole("heading", { name: "Internal review" }).locator("xpath=..");
    await reviewCard.getByLabel("Task status").selectOption("in_progress");
    await expect(reviewCard.getByText("Saved", { exact: true })).toBeVisible();
    await page.getByRole("link", { name: "History", exact: true }).click();
    await expect(page.getByText("Applied a task template with 6 planned tasks")).toBeVisible();
    await expect(page.getByText(/Moved “Internal review” from todo to in progress/)).toBeVisible();
    await page.getByRole("link", { name: "Upcoming", exact: true }).click();

    await page.getByText("Add planned task", { exact: true }).click();
    await page.getByLabel("Task title").fill(task);
    await page.getByLabel("Task deadline").fill(deadline);
    await page.getByRole("button", { name: "Create task" }).click();
    await expect(page.getByRole("heading", { name: task })).toBeVisible();
    await page.getByRole("button", { name: "Assign task", exact: true }).click();
    await expect(page.getByRole("button", { name: "Unassign Producer" })).toBeVisible();

    const taskResponse = await page.request.get(`/api/v1/projects/${projectId}/tasks`);
    expect(taskResponse.ok()).toBe(true);
    const taskRows = (await taskResponse.json()).data as { id: string; title: string }[];
    const taskId = taskRows.find((row) => row.title === task)?.id;
    if (!taskId) throw new Error("The task created by this test was not returned");

    await page.getByRole("link", { name: "Tasks", exact: true }).click();
    await expect(page).toHaveURL(/\/admin\/tasks(?:\?|$)/);
    await expect(page.getByRole("heading", { name: "Tasks", exact: true })).toBeVisible();
    const filters = page.getByRole("form", { name: "Task filters" });
    await expect(filters).toBeVisible();
    await filters.getByLabel("Project").selectOption({ label: project });
    await filters.getByLabel("Priority").selectOption("medium");
    await filters.getByLabel("Deadline status").selectOption("true");
    await filters.getByRole("button", { name: "Apply filters" }).click();
    await expect(page).toHaveURL(/project_id=/);
    const board = page.getByRole("region", { name: "Task results" });
    await expect(board.getByRole("link", { name: task, exact: true })).toBeVisible();
    await expect(board.getByText("Overdue · " + deadline)).toBeVisible();
    const kanban = board.getByLabel("Kanban columns");
    await expect(kanban).toBeVisible();
    expect(await kanban.evaluate((element) => element.scrollWidth > element.clientWidth)).toBe(true);
    expect((await page.getByRole("region", { name: "To do" }).boundingBox())?.width).toBeGreaterThanOrEqual(288);

    await page.getByRole("link", { name: "Table view" }).click();
    await expect(page.getByRole("columnheader", { name: "Assignees" })).toBeVisible();
    await expect(page.getByRole("link", { name: task, exact: true })).toBeVisible();
    await page.getByLabel("Move " + task).selectOption("in_progress");
    await expect(board.getByRole("status")).toContainText("moved to In progress");
    await page.getByRole("link", { name: "Board view" }).click();
    await expect(
      page.getByRole("region", { name: "In progress" }).getByRole("link", { name: task }),
    ).toBeVisible();
    await page.getByRole("link", { name: "Reset filters" }).click();
    await expect(page.getByRole("form", { name: "Task filters" }).getByLabel("Project")).toHaveValue("");
    await page.goto("/admin/dashboard");
    await expect(page.getByRole("heading", { name: "Operations overview" })).toBeVisible();
    await expect(page.getByText("Open tasks", { exact: true })).toBeVisible();
    await expect(page.getByRole("row", { name: /Producer/ })).toBeVisible();

    const producerPage = await browser.newPage();
    producer = producerPage;
    await login(producerPage, "producer");
    await producerPage.getByRole("link", { name: "Inbox" }).click();
    verifyWorkflow("task.assigned", taskId);
    await expect
      .poll(
        async () => {
          const response = await producerPage.request.get("/api/v1/notifications");
          return (await response.json()).data.some(
            (notice: { resource_id: string }) => notice.resource_id === taskId,
          );
        },
        { timeout: 30000 },
      )
      .toBe(true);
    verifyWorkflow("task.deadline_reminder", taskId);
    await producerPage.reload();
    await expect(producerPage.getByRole("link", { name: new RegExp(task) })).toBeVisible();
    await producerPage.goto(projectPath);
    await producerPage.getByLabel("Task status").selectOption("completed");
    await producerPage.getByRole("button", { name: "Update task status" }).click();
    await expect(producerPage.getByText("completed · " + deadline)).toBeVisible();

    if (!client) throw new Error("Client session was not created");
    await client.goto("/client/dashboard");
    await expect(client.getByRole("heading", { name: "Project overview" })).toBeVisible();
    await expect(client.getByText(brief, { exact: true })).toBeVisible();
    await expect(client.getByText("approved", { exact: true })).toBeVisible();
    await client.getByRole("link", { name: "Projects", exact: true }).click();
    await expect(client.getByRole("heading", { name: "Your projects" })).toBeVisible();
    await client.getByRole("link", { name: project, exact: true }).click();
    await expect(client.getByText(milestone, { exact: true })).toBeVisible();
    await client.getByRole("tab", { name: "History" }).click();
    await expect(client.getByRole("heading", { name: "Activity timeline" })).toBeVisible();
    await expect(client.getByText(`Created milestone “${milestone}”`, { exact: true })).toBeVisible();
    await expect(client.getByText("1 of 1 complete · 100%")).toBeVisible();
    await expect(client.getByText(task, { exact: true })).toHaveCount(0);
    await expect(client.getByText("Confidential planning")).toHaveCount(0);

    await page.goto(projectPath);
    await page.getByText("Project settings", { exact: true }).click();
    await page.getByRole("button", { name: "Archive project" }).click();
    await expect(page).toHaveURL(/\/admin\/projects$/);
    archived = true;
    await client.reload();
    await expect(client.getByRole("heading", { name: project })).toHaveCount(0);
  } finally {
    if (projectId && !archived) {
      const cleanupStatus = await archiveTestProject(page, projectId);
      if (cleanupStatus !== 204 && cleanupStatus !== 404) {
        throw new Error(
          `Could not archive test-owned project ${projectId}: ${cleanupStatus}`,
        );
      }
    }
    await producer?.close();
    await client?.close();
  }
});
