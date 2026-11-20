import { expect, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { compose } from "./accounts";
export async function reviewCycle(
  manager: Page,
  client: Page,
  id: string,
  title: string,
) {
  const url = "?item=" + id;
  async function verify(event: string) {
    const data = (
      await (await manager.request.get("/api/v1/content-items/" + id)).json()
    ).data;
    console.log(
      execFileSync(
        "python3",
        [
          "../scripts/verify_workflow.py",
          event,
          id,
          "--revision",
          data.current_revision_id,
        ],
        { encoding: "utf8" },
      ).trim(),
    );
  }
  await manager.goto("/admin/approvals" + url);
  await manager
    .getByRole("button", { name: "Submit for Internal Review" })
    .click();
  const release = manager.getByRole("button", {
    name: "Approve & Release to Client",
    exact: true,
  });
  await release.click();
  const modal = manager.getByRole("dialog");
  await expect(modal).toContainText(title);
  await expect(modal).toContainText("Revision 2");
  await expect(modal).toContainText("visible to the client");
  await modal.getByRole("button", { name: "Cancel" }).click();
  await expect(modal).not.toBeVisible();
  await release.click();
  await manager.keyboard.press("Escape");
  await expect(modal).not.toBeVisible();
  await client.goto("/client/approvals" + url);
  await expect(client.getByText("No deliverable available.")).toBeVisible();
  const restart = process.env.CP4_TEST_WORKER_RESTART === "1";
  if (restart) compose("stop", "worker");
  try {
    await release.click();
    await modal.getByRole("button", { name: "Confirm & Release" }).click();
    await expect(
      manager.getByText("Revision 2 · client review", { exact: true }),
    ).toBeVisible();
  } finally {
    if (restart) compose("start", "worker");
  }
  await verify("content.client_review_requested");
  await client.goto("/client/notifications");
  await client.getByRole("link", { name: new RegExp(title) }).click();
  await expect(client).toHaveURL(new RegExp("/client/approvals[?]item="+id+"$"));
  await expect(
    client.getByText("Revision 2 · pending", { exact: true }),
  ).toBeVisible();
  await client.getByLabel("Client feedback").fill("Revise the headline");
  await client
    .getByRole("button", { name: "Request revision", exact: true })
    .click();
  await expect(
    client.getByText("Revision 2 · revision requested", { exact: true }),
  ).toBeVisible();
  await verify("content.revision_requested");
  await manager.reload();
  await manager.getByText("Edit draft", { exact: true }).click();
  await manager.getByLabel("Headline").fill("New editorial headline");
  await manager.getByRole("button", { name: "Save new revision" }).click();
  await manager
    .getByRole("button", { name: "Submit for Internal Review" })
    .click();
  await release.click();
  await expect(modal).toContainText("Revision 3");
  await modal.getByRole("button", { name: "Confirm & Release" }).click();
  await expect(
    manager.getByText("Revision 3 · client review", { exact: true }),
  ).toBeVisible();
  await verify("content.client_review_requested");
  await client.reload();
  await client
    .getByRole("button", { name: "Approve revision", exact: true })
    .click();
  await expect(
    client.getByText("Revision 3 · approved", { exact: true }),
  ).toBeVisible();
  await verify("content.client_approved");
  await manager.goto("/admin/notifications");
  await expect(
    manager.getByRole("link", {
      name: new RegExp(title + ".*client approved"),
    }),
  ).toBeVisible();
  await manager.goto("/admin/automation");
  await expect(
    manager
      .getByRole("cell", { name: "content.client_approved", exact: true })
      .first(),
  ).toBeVisible();
}
