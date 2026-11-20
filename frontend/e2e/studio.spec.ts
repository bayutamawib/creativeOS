import { reviewCycle } from "./review-cycle";
import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { compose, sign, verifyCreativeTestMode } from "./accounts";
import type { Studio } from "../lib/studio";

function verify(event: string, resource: string) {
  const result = execFileSync(
    "python3",
    ["../scripts/verify_workflow.py", event, resource],
    { encoding: "utf8" },
  );
  expect(result).toContain("fixture");
  console.log(result.trim());
}
test.beforeAll(verifyCreativeTestMode);
test("approved brief reaches human selection, project tasks and a revised internal draft", async ({
  page,
  browser,
}) => {
  test.setTimeout(160000);
  await sign(page, "lead");
  await page.goto("/client/briefs");
  const title = "Studio " + randomUUID();
  await page.getByLabel("Brief title").fill(title);
  await page
    .getByLabel("Campaign objective")
    .fill("Introduce the editorial campaign");
  await page.getByRole("button", { name: "Save draft" }).click();
  await page.getByRole("button", { name: "Submit brief" }).click();
  await expect(page.getByText(/Version 2 · submitted/)).toBeVisible();
  const manager = await browser.newPage();
  try {
    await sign(manager, "manager");
    const url = new URL(page.url());
    const brief = url.searchParams.get("brief")!;
    await manager.goto("/admin/briefs" + url.search);
    await manager.getByRole("button", { name: "Approve brief" }).click();
    await expect(manager.getByText(/Version 3 · approved/)).toBeVisible();
    await manager.goto("/admin/creative-studio?brief=" + brief);
    const choose = manager
      .getByRole("button", { name: "Select direction" })
      .first();
    await expect(choose).toBeVisible({ timeout: 60000 });
    verify("brief.approved", brief);
    await choose.click();
    const pick = manager
      .getByRole("button", { name: "Select plan item" })
      .first();
    await expect(pick).toBeVisible({ timeout: 60000 });
    const studioPath = "/api/v1/briefs/" + brief + "/studio";
    async function state(): Promise<Studio> {
      return (await (await manager.request.get(studioPath)).json()).data;
    }
    const direction = (await state()).proposals.find(
      (p) => p.kind === "direction" && p.decision === "approved",
    )!;
    verify("creative_direction.approved", direction.id);
    await pick.click();
    await manager
      .getByRole("button", { name: "Create draft deliverable" })
      .click();
    await manager
      .getByLabel("Copywriting feedback")
      .fill("Keep the headline concise");
    await manager.getByRole("button", { name: "Suggest copy" }).click();
    await manager
      .getByRole("button", { name: "Save copy as revision" })
      .click();
    await expect(
      manager.getByText("Draft deliverable · Revision 2"),
    ).toBeVisible();
    const final = await state();
    expect(final.jobs.filter((j) => j.status === "completed")).toHaveLength(4);
    expect(final.items).toHaveLength(1);
    const tasks = await (
      await manager.request.get(
        "/api/v1/projects/" +
          url.searchParams.get("project") +
          "/tasks?page_size=100",
      )
    ).json();
    expect(
      tasks.data.filter((t: { title: string }) => t.title.includes(title)),
    ).toHaveLength(2);
    expect((await page.request.get(studioPath)).status()).toBe(403);
    expect(
      (
        await page.request.get("/api/v1/content-items/" + final.items[0].id)
      ).status(),
    ).toBe(403);
    if (process.env.CP3_TEST_WORKER_RESTART === "1") {
      let jobId: string;
      compose("stop", "worker");
      try {
        const queued = manager.waitForResponse(
          (r) =>
            r.url().endsWith("/analyze") && r.request().method() === "POST",
        );
        await manager.getByRole("button", { name: "Analyze brief" }).click();
        const res = await queued;
        expect(res.status()).toBe(202);
        const job = (await res.json()).data;
        expect(job.status).toBe("pending");
        jobId = job.generation_id;
      } finally {
        compose("start", "worker");
      }
      await expect
        .poll(
          async () => (await state()).jobs.find((j) => j.id === jobId)?.status,
        )
        .toBe("completed");
      console.log(
        "PASS queued fixture generation survived worker restart:",
        jobId,
      );
    }
    await reviewCycle(manager,page,final.items[0].id,title);
  } finally {
    await manager.close();
  }
});
