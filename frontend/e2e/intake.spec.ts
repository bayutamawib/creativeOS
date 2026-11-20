import { execFileSync } from "node:child_process";
import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { randomUUID } from "node:crypto";
test("public inquiry to qualified lead, invited client and initial project", async ({
  page,
  browser,
}) => {
  const suffix = randomUUID(),
    company = "Workshop " + suffix,
    email = suffix + "@example.com",
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
  await manager.goto("/login");
  await manager.getByLabel("Email address").fill("manager@example.com");
  await manager
    .getByLabel("Password", { exact: true })
    .fill(
      JSON.parse(readFileSync("../.local/demo-accounts.json", "utf8"))[
        "manager@example.com"
      ],
    );
  await manager.getByRole("button", { name: "Sign in", exact: true }).click();
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
  await manager.close();
});
