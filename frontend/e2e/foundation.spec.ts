import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

function password(email: string): string {
  const accounts = JSON.parse(
    readFileSync(
      path.resolve(process.cwd(), "../.local/demo-accounts.json"),
      "utf8",
    ),
  );
  return accounts[email];
}
async function login(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password(email));
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
}

test("signed-out visitors return to login from both protected portals", async ({
  page,
}) => {
  for (const route of ["/admin/dashboard", "/client/dashboard"]) {
    await page.goto(route);
    await expect(page).toHaveURL(/\/login$/);
  }
});
test("manager session opens agency controls and ends on logout", async ({
  page,
}) => {
  await login(page, "manager@example.com");
  await expect(
    page.getByRole("heading", { name: "Agency members" }),
  ).toBeVisible();
  await page.goto("/client/dashboard");
  await expect(page).toHaveURL(/\/admin\/dashboard$/);
  await expect(page.getByRole("combobox")).toHaveText("Team Member");
  await page.getByRole("button", { name: "Renew session" }).click();
  await expect(page.getByText("Session renewed")).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/admin/dashboard");
  await expect(page).toHaveURL(/\/login$/);
});
test("client membership opens only its client workspace", async ({ page }) => {
  await login(page, "reviewer@example.com");
  await expect(
    page.getByRole("heading", { name: "Northline Studio" }),
  ).toBeVisible();
  await expect(
    page.getByText("Your review access", { exact: false }),
  ).toBeVisible();
  await expect(page.getByText("Grant authority")).toHaveCount(0);
  await page.goto("/admin/dashboard");
  await expect(page).toHaveURL(/\/client\/dashboard$/);
});

test("client admin delegates and revokes project review authority", async ({
  browser,
}) => {
  const owner = await browser.newPage();
  const reviewer = await browser.newPage();
  await login(owner, "lead@example.com");
  await login(reviewer, "reviewer@example.com");
  await expect(
    reviewer.getByText("View and comment", { exact: false }),
  ).toBeVisible();
  const grant = owner.getByRole("button", { name: "Grant authority" });
  await expect(grant).toBeVisible();
  try {
    await grant.click();
    await expect(
      owner.getByRole("button", { name: "Revoke authority" }),
    ).toBeVisible();
    await reviewer.reload();
    await expect(
      reviewer.getByText("Approval and revision requests", { exact: false }),
    ).toBeVisible();
  } finally {
    const revoke = owner.getByRole("button", { name: "Revoke authority" });
    if (await revoke.isVisible()) {
      await revoke.click();
      await expect(grant).toBeVisible();
    }
  }
  await reviewer.reload();
  await expect(
    reviewer.getByText("View and comment", { exact: false }),
  ).toBeVisible();
  await owner.close();
  await reviewer.close();
});
