import { afterEach, expect, it, vi } from "vitest";
import { readiness } from "../lib/readiness";
afterEach(() => vi.unstubAllGlobals());
it("requires a successful ready response", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(Response.json({ status: "ready" })),
  );
  expect(await readiness()).toBe(true);
});
it("reports a lost backend connection", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  expect(await readiness()).toBe(false);
});
