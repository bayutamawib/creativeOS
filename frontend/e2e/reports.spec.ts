import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { sign, verifyCreativeTestMode } from "./accounts";
test("period report is generated, reviewed, released and downloaded by the owning client", async ({
  page,
  browser,
}) => {
  test.setTimeout(150000);
  verifyCreativeTestMode();
  await sign(page, "manager");
  const title = "Report study " + randomUUID();
  const project = await page.evaluate(async (name) => {
    const clients = await (await fetch("/api/v1/clients")).json();
    const organization = clients.data.find(
      (c: { company_name: string }) => c.company_name === "Clover Press",
    );
    const token = document.cookie
      .split("; ")
      .find((c) => c.startsWith("__Host-creative_csrf="))!
      .split("=")[1];
    const res = await fetch("/api/v1/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": token },
      body: JSON.stringify({
        name,
        client_id: organization.id,
        status: "in_progress",
      }),
    });
    if (!res.ok) throw Error("Project setup failed");
    return (await res.json()).data.id;
  }, title);
  await page.getByRole("link", { name: "Reports", exact: true }).click();
  await page.getByLabel("Find project").fill(title);
  await page.getByLabel("Reporting project").selectOption(project);
  await page.getByLabel("Period start").fill("2026-02-01");
  await page.getByLabel("Period end").fill("2026-02-28");
  await page
    .getByRole("button", { name: "Generate report", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: title + " report" }),
  ).toBeVisible();
  await expect(page.getByLabel("Draft narrative")).toContainText(
    "Completed tasks: 0",
    { timeout: 40000 },
  );
  const id = new URL(page.url()).pathname.split("/").pop()!;
  const client = await browser.newPage();
  await sign(client, "publisher");
  expect(
    (await client.request.get("/api/v1/reports/" + id + "/download")).status(),
  ).toBe(404);
  await page.getByRole("button", { name: "Submit for review" }).click();
  await page.getByRole("button", { name: "Publish to client" }).click();
  await expect(
    page.getByText(/2026-02-01 – 2026-02-28 · published/),
  ).toBeVisible();
  await client.getByRole("link", { name: "Reports", exact: true }).click();
  await client
    .getByRole("link", { name: new RegExp(title + ".*2026-02-01") })
    .click();
  await expect(
    client.getByRole("heading", { name: title + " report" }),
  ).toBeVisible();
  const file = client.waitForEvent("download");
  await client.getByText("Download report (JSON)").click();
  expect((await file).suggestedFilename()).toContain(id);
  for (const type of ["report.drafted", "report.published"])
    console.log(
      execFileSync("python3", ["../scripts/verify_workflow.py", type, id], {
        encoding: "utf8",
      }).trim(),
    );
  await client.close();
});
