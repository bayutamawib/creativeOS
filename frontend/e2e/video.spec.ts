import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { compose, sign } from "./accounts";

test("manual cover and authenticated MP4 seek work in both portals", async ({ page, browser }) => {
  test.setTimeout(180000);
  compose("exec", "-T", "backend", "python", "-c", "from app.config import settings; s=settings(); assert s.ai_provider == 'fixture' and s.file_provider == 'local'");
  await sign(page, "manager");
  const organizations = (await (await page.request.get("/api/v1/clients")).json()).data;
  const north = organizations.find((c: { company_name: string }) => c.company_name === "Northline Studio");
  const projectResponse = await page.evaluate(async (data) => {
    const csrf = document.cookie.split("; ").find((v) => v.startsWith("__Host-creative_csrf="))!.split("=")[1];
    const response = await fetch("/api/v1/projects", { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf }, body: JSON.stringify(data) });
    return { status: response.status, body: await response.json() };
  }, { name: "Video review " + randomUUID().slice(0, 6), client_id: north.id, status: "in_progress" });
  expect(projectResponse.status).toBe(201);
  const project = projectResponse.body.data;
  const bytes = await page.evaluate(async () => {
    const canvas = document.createElement("canvas");
    canvas.width = 64; canvas.height = 64;
    const context = canvas.getContext("2d")!;
    const stream = canvas.captureStream(10);
    const recorder = new MediaRecorder(stream, { mimeType: "video/mp4;codecs=avc1.42E01E" });
    const chunks: Blob[] = [];
    recorder.ondataavailable = (event) => chunks.push(event.data);
    recorder.start();
    let frame = 0;
    const timer = setInterval(() => { context.fillStyle = frame++ % 2 ? "#e11d48" : "#1d4ed8"; context.fillRect(0, 0, 64, 64); }, 100);
    await new Promise((resolve) => setTimeout(resolve, 1400));
    clearInterval(timer);
    recorder.stop();
    await new Promise((resolve) => { recorder.onstop = resolve; });
    stream.getTracks().forEach((track) => track.stop());
    return Array.from(new Uint8Array(await new Blob(chunks).arrayBuffer()));
  });
  await page.goto("/admin/projects/" + project.id);
  await page.getByText("Upload project video", { exact: true }).click();
  await page.getByLabel("MP4 video").setInputFiles({ name: "review.mp4", mimeType: "video/mp4", buffer: Buffer.from(bytes) });
  await page.getByLabel("Manual cover image").setInputFiles({ name: "review.png", mimeType: "image/png", buffer: readFileSync("e2e/fixtures/orchard.png") });
  await page.getByLabel("Video visibility").selectOption("client_visible");
  await page.getByRole("button", { name: "Upload video" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Video and cover uploaded" })).toBeVisible();
  const files = (await (await page.request.get("/api/v1/files?portal=agency&project_id=" + project.id)).json()).data;
  const video = files.find((f: { mime_type: string }) => f.mime_type === "video/mp4");
  expect(video.cover_file_id).toBeTruthy();
  await page.getByRole("button", { name: "Play review.mp4" }).click();
  const agencyDialog = page.getByRole("dialog", { name: "Video preview review.mp4" });
  await expect(agencyDialog.locator("video")).toHaveJSProperty("readyState", 4);
  await agencyDialog.getByRole("button", { name: "Fullscreen" }).click();
  await expect.poll(() => page.evaluate(() => Boolean(document.fullscreenElement))).toBe(true);
  await page.evaluate(() => document.exitFullscreen());
  await agencyDialog.getByRole("button", { name: "Close preview" }).click();
  const client = await browser.newPage();
  try {
    await sign(client, "lead");
    const ranged = await client.request.get("/api/v1/files/" + video.id + "/stream?portal=client", { headers: { Range: "bytes=0-15" } });
    expect(ranged.status()).toBe(206);
    expect((await ranged.body()).length).toBe(16);
    await client.goto("/client/projects/" + project.id);
    await client.getByRole("button", { name: "Play review.mp4" }).click();
    const dialog = client.getByRole("dialog", { name: "Video preview review.mp4" });
    await expect(dialog).toBeVisible();
    const player = dialog.locator("video");
    await expect(player).toHaveJSProperty("readyState", 4);
    const duration = await player.evaluate((node: HTMLVideoElement) => node.duration);
    expect(duration).toBeGreaterThan(0.5);
    await player.evaluate(async (node: HTMLVideoElement) => {
      node.currentTime = Math.min(0.5, node.duration / 2);
      await new Promise<void>((resolve) => node.addEventListener("seeked", () => resolve(), { once: true }));
    });
    expect(await player.evaluate((node: HTMLVideoElement) => node.currentTime)).toBeGreaterThan(0.1);
    await dialog.getByRole("button", { name: "Close preview" }).click();
    await expect(dialog).not.toBeVisible();
    await page.goto("/admin/projects/" + project.id);
    await page.getByText("Upload project video", { exact: true }).click();
    await page.getByLabel("MP4 video").setInputFiles({ name: "no-cover.mp4", mimeType: "video/mp4", buffer: Buffer.from(bytes) });
    await page.getByLabel("Video visibility").selectOption("client_visible");
    await page.getByRole("button", { name: "Upload video" }).click();
    await expect(page.getByRole("status").filter({ hasText: "Video uploaded" })).toBeVisible();
    const refreshed = (await (await page.request.get("/api/v1/projects?portal=agency&q=" + encodeURIComponent(project.name))).json()).data[0];
    expect(refreshed.cover_video_id).toBeTruthy();
    expect(refreshed.cover_file_id).toBeNull();
    await page.goto("/admin/projects?q=" + encodeURIComponent(project.name));
    await expect(page.getByRole("link", { name: project.name })).toContainText("▶");
    await client.goto("/client/projects/" + project.id);
    await client.getByRole("button", { name: "Play no-cover.mp4" }).click();
    await expect(client.getByRole("dialog", { name: "Video preview no-cover.mp4" }).locator("video")).toHaveJSProperty("readyState", 4);
    await client.keyboard.press("Escape");
    await page.goto("/admin/projects/" + project.id);
    await page.getByText("Upload project video", { exact: true }).click();
    await page.getByLabel("MP4 video").setInputFiles({ name: "private-review.mp4", mimeType: "video/mp4", buffer: Buffer.from(bytes) });
    await page.getByRole("button", { name: "Upload video" }).click();
    await expect(page.getByRole("status").filter({ hasText: "Video uploaded" })).toBeVisible();
    const privateFiles = (await (await page.request.get("/api/v1/files?portal=agency&project_id=" + project.id)).json()).data;
    const privateVideo = privateFiles.find((f: { file_name: string }) => f.file_name === "private-review.mp4");
    expect((await client.request.get("/api/v1/files/" + privateVideo.id + "/stream?portal=client", { headers: { Range: "bytes=0-15" } })).status()).toBe(404);

    async function post(actor: typeof page, path: string, data: object = {}) {
      const result = await actor.evaluate(async ({ path, data }) => {
        const csrf = document.cookie.split("; ").find((v) => v.startsWith("__Host-creative_csrf="))!.split("=")[1];
        const response = await fetch("/api/v1" + path, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf, "Idempotency-Key": crypto.randomUUID() },
          body: JSON.stringify(data),
        });
        return { status: response.status, body: await response.json() };
      }, { path, data });
      expect(result.status, path).toBeLessThan(300);
      return result.body.data;
    }
    const brief = await post(client, "/projects/" + project.id + "/briefs", { title: "Video review", objective: "Review a fictional clip", preferred_channels: ["Instagram"] });
    await post(client, "/briefs/" + brief.id + "/submit", { expected_version: 1 });
    await post(page, "/briefs/" + brief.id + "/approve", { expected_version: 2 });
    const briefPath = "/briefs/" + brief.id;
    async function generate(action: string, data: object = {}) {
      await post(page, briefPath + "/" + action, data);
      compose("exec", "-T", "backend", "python", "-c", "from app.ai import runner; assert runner.execute_one()");
    }
    await generate("analyze");
    await generate("generate-creative-direction");
    const proposals = (await (await page.request.get("/api/v1" + briefPath + "/proposals")).json()).data;
    const direction = proposals.find((p: { kind: string }) => p.kind === "direction");
    await post(page, "/proposals/" + direction.id + "/approve");
    await generate("generate-content-plan", { direction_proposal_id: direction.id });
    const plan = (await (await page.request.get("/api/v1" + briefPath + "/proposals")).json()).data.find((p: { kind: string }) => p.kind === "plan_item");
    await post(page, "/proposals/" + plan.id + "/approve");
    const item = await post(page, "/projects/" + project.id + "/content-items", { proposal_id: plan.id });
    const revision = await post(page, "/content-items/" + item.id + "/revisions", { revision_id: item.current_revision_id, headline: "Video review", caption: "Please review this clip", attachment_ids: [privateVideo.id] });
    await post(page, "/content-items/" + item.id + "/submit-for-internal-review", { revision_id: revision.current_revision_id });
    await page.goto("/admin/approvals?item=" + item.id);
    await page.getByRole("button", { name: "Approve & Release to Client", exact: true }).click();
    await page.getByRole("button", { name: "Confirm & Release", exact: true }).click();
    await client.goto("/client/approvals?item=" + item.id);
    await client.getByRole("button", { name: "Play private-review.mp4" }).click();
    await expect(client.getByRole("dialog", { name: "Video preview private-review.mp4" }).locator("video")).toHaveJSProperty("readyState", 4);
    await client.keyboard.press("Escape");
    await client.getByRole("button", { name: "Approve revision" }).click();
    await expect(client.getByRole("status").filter({ hasText: "Saved" })).toBeVisible();
  } finally { await client.close(); }
});
