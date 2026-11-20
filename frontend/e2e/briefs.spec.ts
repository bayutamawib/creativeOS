import { test, expect } from "@playwright/test";
import { sign, verifyCreativeTestMode } from "./accounts";
import { randomUUID } from "node:crypto";
test.beforeAll(verifyCreativeTestMode);
test("client uploads references and submits a brief for agency approval", async ({
  page,
  browser,
}) => {
  const title = "Launch brief " + randomUUID(),
    file = randomUUID() + ".txt";
  await sign(page, "lead");
  await page.goto("/client/briefs/new");
  await page.getByText("Upload project file", { exact: true }).click();
  await page.locator("input[type=file]").setInputFiles({
    name: file,
    mimeType: "text/plain",
    buffer: Buffer.from("Synthetic brand guide"),
  });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await expect(page.getByRole("link", { name: file })).toBeVisible();
  await page.getByLabel("Brief title").fill(title);
  await page
    .getByLabel("Campaign objective")
    .fill("Introduce a new editorial collection");
  await page.getByLabel(file, { exact: true }).check();
  await page.getByRole("button", { name: "Save draft" }).click();
  await page.getByRole("button", { name: "Submit brief" }).click();
  await expect(page.getByText(/Version 2 · submitted/)).toBeVisible();
  const manager = await browser.newPage();
  await sign(manager, "manager");
  const url = new URL(page.url());
  await manager.goto("/admin/briefs" + url.search);
  await manager.getByRole("button", { name: "Approve brief" }).click();
  await expect(manager.getByText(/Version 3 · approved/)).toBeVisible();
  await page.reload();
  await expect(page.getByText(/Version 3 · approved/)).toBeVisible();
  await page.getByText("Approval history", { exact: true }).click();
  await expect(page.getByText("Version 3 · " + title)).toBeVisible();
  await page.goto("/client/files");
  await expect(page.getByRole("link", { name: file })).toBeVisible();
  await manager.close();
});
