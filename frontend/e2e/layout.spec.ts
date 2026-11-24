import { expect, test } from "@playwright/test";
import { sign } from "./accounts";

test("agency workspace uses the viewport without page-level overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await sign(page, "manager");

  for (const width of [390, 768, 1440, 1536]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    await page.goto("/admin/dashboard");
    await expect(page.getByRole("heading", { name: "Operations overview" })).toBeVisible();
    const main = page.locator("main");
    const box = await main.boundingBox();
    expect(box?.width).toBeGreaterThanOrEqual(width - 1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    if (width === 390) {
      await expect(page.getByText("Workspace menu", { exact: true })).toBeVisible();
      await page.getByText("Workspace menu", { exact: true }).click();
      await expect(page.getByRole("navigation", { name: "Agency navigation" })).toBeVisible();
    } else {
      await expect(page.getByRole("navigation", { name: "Agency navigation" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Overview", exact: true })).toHaveAttribute(
        "aria-current",
        "page",
      );
    }
  }

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/admin/tasks");
  const board = page.getByLabel("Kanban columns");
  if (await board.count()) {
    await expect(board).toBeVisible();
    const firstColumn = board.locator(":scope > section").first();
    expect((await firstColumn.boundingBox())?.width).toBeGreaterThanOrEqual(288);
    expect(await board.evaluate((element) => element.scrollWidth >= element.clientWidth)).toBe(true);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(1440);
});
