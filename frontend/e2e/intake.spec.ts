import { verifyCreativeTestMode, sign } from "./accounts";
import { productionJourney } from "./production-journey";
import { capture } from "./portfolio-capture";
import { execFileSync } from "node:child_process";
import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";
test("portfolio journey from public inquiry to client sign-off and published report", async ({
  page,
  browser,
}) => {
  test.setTimeout(240000);
  verifyCreativeTestMode();
  const suffix = randomUUID().slice(0, 8),
    company = "Aster Press " + suffix,
    email = randomUUID() + "@example.com",
    password = randomUUID();
  await page.goto("/inquiry");
  await page.getByLabel("Company name").fill(company);
  await page.getByLabel("Contact name").fill("Synthetic Contact");
  await page.getByLabel("Email address").fill(email);
  const receipt = page.waitForResponse(
    (r) =>
      r.url().endsWith("/public/inquiries") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Submit inquiry" }).click();
  const leadId = (await (await receipt).json()).data.id;
  console.log(
    execFileSync(
      "python3",
      ["../scripts/verify_workflow.py", "lead.created", leadId],
      { encoding: "utf8" },
    ).trim(),
  );
  await expect(
    page.getByRole("heading", { name: "Inquiry received" }),
  ).toBeVisible();
  const manager = await browser.newPage();
  await sign(manager, "manager");
  await manager.getByRole("link", { name: "Leads", exact: true }).click();
  await manager.getByRole("link", { name: company }).click();
  await manager.getByLabel("Lead status").selectOption("qualified");
  await manager.getByRole("button", { name: "Save review" }).click();
  await manager.getByLabel("Initial project name").fill("Launch " + suffix);
  manager.once("dialog", (dialog) => dialog.accept());
  await manager.getByRole("button", { name: "Convert lead" }).click();
  await manager.getByRole("button", { name: "Create invitation" }).click();
  await expect(manager.getByLabel("Private invitation link")).toBeVisible();
  await page.goto(
    await manager.getByLabel("Private invitation link").inputValue(),
  );
  await page.getByLabel("Name", { exact: true }).fill("Synthetic Contact");
  await page.getByLabel("New password").fill(password);
  await page.getByRole("button", { name: "Accept invitation" }).click();
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: company })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Launch " + suffix }),
  ).toBeVisible();
  const projectName = "Launch " + suffix;
  const projectLink = await page
    .getByRole("link", { name: projectName, exact: true })
    .getAttribute("href");
  const project = new URL(projectLink!, page.url()).searchParams.get(
    "project",
  )!;
  const produced = await productionJourney(
    page,
    manager,
    "Field Notes " + suffix,
    project,
    true,
  );
  expect(produced.project).toBe(project);
  await manager.goto("/admin/projects/" + project);
  await manager.getByLabel("Agency member").selectOption({ label: "Producer" });
  await manager.getByRole("button", { name: "Add project member" }).click();
  const assignment = manager.waitForResponse(
    (r) => r.url().endsWith("/assign") && r.request().method() === "POST",
  );
  await manager
    .getByRole("button", { name: "Assign task", exact: true })
    .first()
    .click();
  const assigned = await assignment;
  expect(assigned.ok()).toBe(true);
  const task = new URL(assigned.url()).pathname.split("/").at(-2)!;
  console.log(
    execFileSync(
      "python3",
      ["../scripts/verify_workflow.py", "task.assigned", task],
      { encoding: "utf8" },
    ).trim(),
  );
  await manager.getByLabel("Task status").first().selectOption("completed");
  await manager
    .getByRole("button", { name: "Update task status" })
    .first()
    .click();
  await expect(manager.getByText(/^completed ·/).first()).toBeVisible();
  await manager.goto("/admin/reports");
  await manager.getByLabel("Find project").fill(projectName);
  await manager.getByLabel("Reporting project").selectOption(project);
  // Include this session in any configured agency timezone, even across midnight.
  const day = (offset: number) =>
    new Date(Date.now() + offset * 86400000).toISOString().slice(0, 10);
  await manager.getByLabel("Period start").fill(day(-1));
  await manager.getByLabel("Period end").fill(day(1));
  await manager
    .getByRole("button", { name: "Generate report", exact: true })
    .click();
  await expect(manager.getByLabel("Draft narrative")).toContainText(
    "Completed tasks: 1",
    { timeout: 40000 },
  );
  const id = new URL(manager.url()).pathname.split("/").pop()!;
  const reportApi = "/api/v1/reports/" + id;
  expect((await page.request.get(reportApi)).status()).toBe(404);
  await manager.getByRole("button", { name: "Submit for review" }).click();
  await manager.getByRole("button", { name: "Publish to client" }).click();
  await expect(manager.getByText(/· published$/)).toBeVisible();
  await page.goto("/client/reports/" + id);
  await expect(
    page.getByRole("heading", { name: projectName + " report" }),
  ).toBeVisible();
  const report = (await (await page.request.get(reportApi)).json()).data;
  expect(report).toMatchObject({
    project_id: project,
    status: "published",
    metrics: {
      total_tasks: 2,
      completed_tasks: 1,
      approvals_in_period: 1,
      revisions_requested_in_period: 1,
    },
  });
  await capture(page, "published-report");
  for (const event of ["report.drafted", "report.published"])
    console.log(
      execFileSync("python3", ["../scripts/verify_workflow.py", event, id], {
        encoding: "utf8",
      }).trim(),
    );
  console.log(
    "PORTFOLIO",
    JSON.stringify({ lead: leadId, ...produced, report: id }),
  );
  await manager.close();
});
