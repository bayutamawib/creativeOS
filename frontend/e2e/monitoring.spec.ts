import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { execFileSync } from "node:child_process";
import { sign } from "./accounts";
test("manager inspects workflow receipts and executes the synthetic evaluation", async ({
  page,
  browser,
}) => {
  test.setTimeout(90000);
  await sign(page, "manager");
  const receipt = await page.request.post("/api/v1/public/inquiries", {
    headers: { Origin: new URL(page.url()).origin },
    data: {
      company_name: "Monitor sample",
      contact_name: "Synthetic contact",
      email: randomUUID() + "@example.com",
    },
  });
  expect(receipt.status()).toBe(201);
  const lead = (await receipt.json()).data.id;
  console.log(
    execFileSync(
      "python3",
      ["../scripts/verify_workflow.py", "lead.created", lead],
      { encoding: "utf8" },
    ).trim(),
  );
  const events = (await (await page.request.get("/api/v1/admin/outbox")).json())
    .data;
  const event = events.find(
    (e: { resource_id: string }) => e.resource_id === lead,
  );
  expect(event).toBeDefined();
  await page.getByRole("link", { name: "Automation", exact: true }).click();
  for (const name of [
    "Workflow runs",
    "Generation jobs",
    "Delivery attempts",
  ]) {
    await page.getByRole("link", { name, exact: true }).click();
    await expect(
      page.getByRole("heading", { name, exact: true }),
    ).toBeVisible();
  }
  const deliveryLink = page
    .getByRole("table")
    .getByRole("link", { name: event.id, exact: true })
    .first();
  await deliveryLink.click();
  await expect(
    page.getByRole("heading", { name: "Processing receipts" }),
  ).toBeVisible();
  await expect(
    page.getByText("development-inbox", { exact: true }).first(),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Automation activity", exact: true })
    .click();
  await page
    .getByRole("navigation", { name: "Activity views" })
    .getByRole("link", { name: "AI evaluations", exact: true })
    .click();
  await page.getByRole("button", { name: "Run fixture evaluation" }).click();
  await expect(
    page.getByRole("heading", { name: "Evaluation results" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "56 / 56 automated cases passed" }),
  ).toBeVisible();
  await expect(
    page.getByText("No human scores recorded. Semantic quality is unassessed."),
  ).toBeVisible();
  await page
    .getByText("brief-01/brief_analysis · Passed", { exact: true })
    .click();
  await expect(
    page.getByText("Save human review", { exact: true }).first(),
  ).toBeVisible();
  const id = new URL(page.url()).pathname.split("/").pop();
  const api = (
    await (await page.request.get("/api/v1/admin/evaluations/" + id)).json()
  ).data;
  expect(api.aggregates.schema_valid).toBe(50);
  expect(api.cases).toHaveLength(56);
  expect(api.human.reviewed).toBe(0);
  console.log("Persisted evaluation", id, api.dataset_hash, api.aggregates);
  const client = await browser.newPage();
  await sign(client, "publisher");
  for (const url of [
    "/admin/evaluations/" + id,
    "/admin/generation-jobs",
    "/admin/workflow-runs",
    "/admin/delivery-attempts",
  ])
    expect((await client.request.get("/api/v1" + url)).status()).toBe(403);
  await client.close();
});
