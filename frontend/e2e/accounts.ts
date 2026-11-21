import { expect, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
export async function sign(page: Page, name: string) {
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

export function compose(...args: string[]) {
  return execFileSync("docker", ["compose", ...args], { cwd: ".." });
}

export function startWorkerAndWait() {
  compose(
    "up",
    "-d",
    "--no-deps",
    "--no-recreate",
    "--no-build",
    "--wait",
    "--wait-timeout",
    "60",
    "worker",
  );
}

export function verifyCreativeTestMode() {
  // These journeys upload files and approve briefs, which starts paid providers when configured.
  for (const service of ["backend", "worker"])
    compose(
      "exec",
      "-T",
      service,
      "python",
      "-c",
      "from app.config import settings; s=settings(); assert s.ai_provider == 'fixture' and s.ai_model == 'fixture-v1' and s.file_provider == 'local', 'Creative browser tests require fixture AI and local storage'",
    );
}
