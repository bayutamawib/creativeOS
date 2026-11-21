import type { Page } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { join } from "node:path";

// Opt in only on an isolated stack containing synthetic portfolio data.
export async function capture(page: Page, name: string) {
  const directory = process.env.PORTFOLIO_SCREENSHOT_DIR;
  if (!directory) return;
  await mkdir(directory, { recursive: true });
  await page.screenshot({
    path: join(directory, name + ".png"),
    animations: "disabled",
  });
}
