import { expect, test, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { mkdir } from "node:fs/promises";
import { join } from "node:path";
import { sign, verifyCreativeTestMode } from "./accounts";

test("project and exact revision media remain private until release", async ({
  page,
  browser,
}) => {
  test.setTimeout(210000);
  verifyCreativeTestMode();
  await page.setViewportSize({ width: 1440, height: 1050 });
  await sign(page, "manager");
  async function post(p: Page, path: string, data: object) {
    const response = await p.evaluate(
      async ({ path, data }) => {
        const csrf = document.cookie
          .split("; ")
          .find((v) => v.startsWith("__Host-creative_csrf="))!
          .split("=")[1];
        const r = await fetch("/api/v1" + path, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
          body: JSON.stringify(data),
        });
        return { status: r.status, body: await r.json() };
      },
      { path, data },
    );
    expect(response.status).toBeLessThan(300);
    return response.body.data;
  }
  async function capture(p: Page, name: string) {
    if (!process.env.MEDIA_SCREENSHOT_DIR) return;
    await mkdir(process.env.MEDIA_SCREENSHOT_DIR, { recursive: true });
    await p.locator("img").evaluateAll((images) =>
      Promise.all(
        images
          .filter((image) => {
            const r = image.getBoundingClientRect();
            return r.top < window.innerHeight && r.bottom > 0;
          })
          .map((image) => (image as HTMLImageElement).decode().catch(() => {})),
      ),
    );

    await p.screenshot({
      path: join(process.env.MEDIA_SCREENSHOT_DIR, name + ".png"),
      animations: "disabled",
    });
  }
  const organizations = (
    await (await page.request.get("/api/v1/clients")).json()
  ).data;
  const north = organizations.find(
    (c: { company_name: string }) => c.company_name === "Northline Studio",
  );
  const title = "Orchard collection " + randomUUID().slice(0, 6);
  const project = await post(page, "/projects", {
    name: title,
    client_id: north.id,
    status: "in_progress",
    due_date: "2027-02-01",
  });
  const client = await browser.newPage(),
    foreign = await browser.newPage();
  try {
    await sign(client, "lead");
    await sign(foreign, "publisher");
    await page.goto("/admin/projects/" + project.id);
    await page.getByText("Upload project image", { exact: true }).click();
    const png = readFileSync("e2e/fixtures/orchard.png");
    await page.getByLabel("Project image", { exact: true }).setInputFiles({
      name: "Orchard shared.png",
      mimeType: "image/png",
      buffer: png,
    });
    await page.getByLabel("Image visibility").selectOption("client_visible");
    await Promise.all([
      page.waitForResponse(
        (r) =>
          r.url().includes("/files/upload?") && r.request().method() === "POST",
      ),
      page.getByRole("button", { name: "Upload image", exact: true }).click(),
    ]);
    await expect(
      page.getByRole("status").filter({ hasText: "Image uploaded" }),
    ).toBeVisible();
    const files = (
      await (
        await page.request.get(
          "/api/v1/files?portal=agency&project_id=" + project.id,
        )
      ).json()
    ).data;
    const shared = files.find(
      (f: { file_name: string }) => f.file_name === "Orchard shared.png",
    ).id;
    await page.goto("/admin/projects?q=" + encodeURIComponent(title));
    await expect(
      page.getByRole("link", { name: title, exact: true }),
    ).toBeVisible();
    await expect(page.getByAltText(title + " project image")).toHaveJSProperty(
      "naturalWidth",
      640,
    );
    await capture(page, "agency-project-gallery");
    await client.goto("/client/projects");
    await expect(
      client.getByAltText(title + " project image"),
    ).toHaveJSProperty("naturalWidth", 640);
    await capture(client, "client-project-gallery");
    await client.goto("/client/projects/" + project.id);
    const preview = client.getByRole("button", {
      name: "Preview Orchard shared.png",
      exact: true,
    });
    await preview.click();
    const dialog = client.getByRole("dialog", {
      name: "Image preview Orchard shared.png",
      exact: true,
    });
    await expect(dialog).toBeVisible();
    await expect(
      dialog.getByRole("button", { name: "Close preview" }),
    ).toBeFocused();
    await expect(dialog.getByAltText("Orchard shared.png")).toHaveJSProperty(
      "naturalWidth",
      900,
    );
    await capture(client, "client-image-preview");
    await client.keyboard.press("Escape");
    await expect(dialog).not.toBeVisible();
    await expect(preview).toBeFocused();
    for (const kind of ["thumbnail", "preview", "download"]) {
      expect(
        (
          await foreign.request.get(
            "/api/v1/files/" + shared + "/" + kind + "?portal=client",
          )
        ).status(),
      ).toBe(404);
    }
    await page.goto("/admin/projects/" + project.id);
    await page.getByText("Upload project image", { exact: true }).click();
    await page.getByLabel("Project image", { exact: true }).setInputFiles({
      name: "Private revision.png",
      mimeType: "image/png",
      buffer: png,
    });
    await Promise.all([
      page.waitForResponse(
        (r) =>
          r.url().includes("/files/upload?") && r.request().method() === "POST",
      ),
      page.getByRole("button", { name: "Upload image", exact: true }).click(),
    ]);
    await expect(
      page.getByRole("status").filter({ hasText: "Image uploaded" }),
    ).toBeVisible();
    const privateFiles = (
      await (
        await page.request.get(
          "/api/v1/files?portal=agency&project_id=" + project.id,
        )
      ).json()
    ).data;
    const privateId = privateFiles.find(
      (f: { file_name: string }) => f.file_name === "Private revision.png",
    ).id;
    expect(
      (
        await client.request.get("/api/v1/files/" + privateId + "/thumbnail")
      ).status(),
    ).toBe(404);
    const brief = await post(client, "/projects/" + project.id + "/briefs", {
      title,
      objective: "Launch a fictional orchard collection",
    });
    await post(client, "/briefs/" + brief.id + "/submit", {
      expected_version: 1,
    });
    await post(page, "/briefs/" + brief.id + "/approve", {
      expected_version: 2,
    });
    await page.goto("/admin/creative-studio?brief=" + brief.id);
    await page
      .getByRole("button", { name: "Select direction" })
      .first()
      .click({ timeout: 60000 });
    await page
      .getByRole("button", { name: "Select plan item" })
      .first()
      .click({ timeout: 60000 });
    await Promise.all([
      page.waitForResponse(
        (r) =>
          r.url().endsWith("/content-items") && r.request().method() === "POST",
      ),
      page.getByRole("button", { name: "Create draft deliverable" }).click(),
    ]);
    const state = (
      await (
        await page.request.get("/api/v1/briefs/" + brief.id + "/studio")
      ).json()
    ).data;
    const item = state.items[0];
    const updated = await post(
      page,
      "/content-items/" + item.id + "/revisions",
      {
        revision_id: item.current_revision_id,
        headline: "Orchard collection",
        caption: "Synthetic editorial image",
        attachment_ids: [privateId],
      },
    );
    await post(
      page,
      "/content-items/" + item.id + "/submit-for-internal-review",
      { revision_id: updated.current_revision_id },
    );
    await page.goto("/admin/approvals?item=" + item.id);
    await page
      .getByRole("button", {
        name: "Preview Private revision.png",
        exact: true,
      })
      .click();
    await expect(
      page.getByRole("dialog", { name: "Image preview Private revision.png" }),
    ).toBeVisible();
    await page.keyboard.press("Escape");
    await page
      .getByRole("button", { name: "Approve & Release to Client", exact: true })
      .click();
    const confirmation = page.getByRole("dialog");
    await expect(confirmation).toContainText("Revision 2");
    await confirmation
      .getByRole("button", { name: "Cancel", exact: true })
      .click();
    expect(
      (
        await client.request.get("/api/v1/files/" + privateId + "/preview")
      ).status(),
    ).toBe(404);
    await page
      .getByRole("button", { name: "Approve & Release to Client", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Confirm & Release", exact: true })
      .click();
    await expect(
      page.getByText("Revision 2 · client review", { exact: true }),
    ).toBeVisible();
    await client.goto("/client/approvals?item=" + item.id);
    await client
      .getByRole("button", {
        name: "Preview Private revision.png",
        exact: true,
      })
      .click();
    await expect(client.getByRole("dialog")).toContainText("Revision 2");
    await expect(
      client.getByRole("dialog").getByAltText("Private revision.png"),
    ).toHaveJSProperty("naturalWidth", 900);
    await capture(client, "released-revision-preview");
    await client.keyboard.press("Escape");
    await post(page, "/content-items/" + item.id + "/revisions", {
      revision_id: updated.current_revision_id,
      headline: "Unreleased replacement",
      caption: "Private draft",
      attachment_ids: [],
    });
    await client.reload();
    await expect(
      client.getByRole("button", { name: "Preview Private revision.png" }),
    ).toBeVisible();
    await expect(
      client.getByText("Unreleased replacement", { exact: true }),
    ).toHaveCount(0);
    await client.setViewportSize({ width: 375, height: 812 });
    await client.goto("/client/projects/" + project.id);
    await expect(
      client.getByRole("button", { name: "Preview Orchard shared.png" }),
    ).toBeVisible();
    expect(
      await client.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(375);
    await client
      .getByRole("heading", { name: "Creative assets", exact: true })
      .evaluate((el) => el.scrollIntoView({ block: "start" }));
    await expect(
      client
        .getByRole("button", {
          name: "Preview Orchard shared.png",
          exact: true,
        })
        .getByAltText("Orchard shared.png"),
    ).toHaveJSProperty("naturalWidth", 640);
    await capture(client, "client-mobile-gallery");
    await client
      .getByRole("button", { name: "Preview Orchard shared.png" })
      .click();
    await expect(client.getByRole("dialog")).toBeVisible();
    expect(
      await client.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(375);
    await client.keyboard.press("Escape");
    console.log(
      "PASS same-origin image previews, exact revision release, client isolation and mobile layout",
      project.id,
    );
  } finally {
    await client.close();
    await foreign.close();
  }
});
