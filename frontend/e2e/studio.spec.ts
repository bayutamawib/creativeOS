import { test } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { sign, verifyCreativeTestMode } from "./accounts";
import { productionJourney } from "./production-journey";

test.beforeAll(verifyCreativeTestMode);
test("approved brief reaches human selection, project tasks and a revised internal draft", async ({
  page,
  browser,
}) => {
  test.setTimeout(160000);
  await sign(page, "lead");
  const manager = await browser.newPage();
  try {
    await sign(manager, "manager");
    await productionJourney(page, manager, "Studio " + randomUUID());
  } finally {
    await manager.close();
  }
});
