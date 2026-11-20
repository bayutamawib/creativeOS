import { execFileSync } from "node:child_process";
import { test, expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { randomUUID } from "node:crypto";
async function login(page: Page, name: string) {
  const email = name + "@example.com";
  await page.goto("/login");
  await page.getByLabel("Email address").fill(email);
  await page
    .getByLabel("Password", { exact: true })
    .fill(
      JSON.parse(readFileSync("../.local/demo-accounts.json", "utf8"))[email],
    );
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/dashboard/);
}
test("agency project management, task notification and client-safe milestones", async ({
  page,
  browser,
}) => {
  test.setTimeout(180000);
  // A date two days ago is overdue in every supported agency timezone.
  const deadline = new Date(Date.now() - 2 * 86400000).toISOString().slice(0, 10);
  const suffix = randomUUID(),
    project = "Z Campaign " + suffix,
    task = "Internal production " + suffix,
    milestone = "Public launch " + suffix;
  await login(page, "manager");
  await page.getByRole("link", { name: "Projects", exact: true }).click();
  await page.getByText("Create project", { exact: true }).first().click();
  await page
    .getByLabel("Client organization")
    .selectOption({ label: "Clover Press" });
  await page.getByLabel("Project name", { exact: true }).fill(project);
  await page
    .getByLabel("Internal project description")
    .fill("Confidential planning");
  await page
    .getByRole("button", { name: "Create project", exact: true })
    .click();
  await expect(page.getByRole("heading", { name: project })).toBeVisible();
  await page.getByLabel("Agency member").selectOption({ label: "Producer" });
  await page.getByRole("button", { name: "Add project member" }).click();
  await expect(
    page.getByRole("button", { name: "Remove Producer" }),
  ).toBeVisible();
  await page.getByText("Add milestone", { exact: true }).click();
  await page.getByLabel("Milestone name").fill(milestone);
  await page.getByLabel("Milestone status").selectOption("completed");
  await page.getByLabel("Release milestone to client").check();
  await page.getByRole("button", { name: "Create milestone" }).click();
  await expect(
    page.locator("strong").filter({ hasText: milestone }),
  ).toBeVisible();
  await page.getByText("Add task", { exact: true }).click();
  await page.getByLabel("Task title").fill(task);
  await page.getByLabel("Task deadline").fill(deadline);
  await page.getByRole("button", { name: "Create task" }).click();
  await expect(page.getByRole("heading", { name: task })).toBeVisible();
  await page.getByRole("button", { name: "Assign task", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Unassign Producer" }),
  ).toBeVisible();
  const producer = await browser.newPage();
  await login(producer, "producer");
  await producer.getByRole("link", { name: "Inbox" }).click();
  const projectPath = new URL(page.url()).pathname;
  const tasks = await page.request.get(
    "/api/v1/projects/" + projectPath.split("/").pop() + "/tasks",
  );
  const id = (await tasks.json()).data[0].id;
  console.log(
    execFileSync(
      "python3",
      ["../scripts/verify_workflow.py", "task.assigned", id],
      { encoding: "utf8" },
    ).trim(),
  );
  await expect
    .poll(
      async () => {
        const r = await producer.request.get("/api/v1/notifications");
        return (await r.json()).data.some(
          (n: { resource_id: string }) => n.resource_id === id,
        );
      },
      { timeout: 30000 },
    )
    .toBe(true);
  console.log(
    execFileSync(
      "python3",
      ["../scripts/verify_workflow.py", "task.deadline_reminder", id],
      { encoding: "utf8" },
    ).trim(),
  );
  await producer.reload();
  await expect(
    producer.getByRole("link", { name: new RegExp(task) }),
  ).toBeVisible();
  await producer.goto(projectPath);
  await producer.getByLabel("Task status").selectOption("completed");
  await producer.getByRole("button", { name: "Update task status" }).click();
  await expect(producer.getByText("completed · " + deadline)).toBeVisible();
  const client = await browser.newPage();
  await login(client, "publisher");
  await client.getByRole("link", { name: "Projects", exact: true }).click();
  await expect(
    client.getByRole("heading", { name: "Your projects" }),
  ).toBeVisible();
  await client.getByRole("link", { name: project, exact: true }).click();
  await expect(client.getByText(milestone, { exact: true })).toBeVisible();
  await expect(client.getByText("1 of 1 complete · 100%")).toBeVisible();
  await expect(client.getByText(task, { exact: true })).toHaveCount(0);
  await expect(client.getByText("Confidential planning")).toHaveCount(0);
  await page.getByText("Project settings", { exact: true }).click();
  await page.getByRole("button", { name: "Archive project" }).click();
  await expect(page).toHaveURL(/\/admin\/projects$/);
  await client.reload();
  await expect(client.getByRole("heading", { name: project })).toHaveCount(0);
  await producer.close();
  await client.close();
});
