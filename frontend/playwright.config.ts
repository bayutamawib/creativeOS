import { defineConfig } from "@playwright/test";

export default defineConfig({
  timeout: 90_000,
  expect: { timeout: 15_000 },
  workers: 1,
  testDir: "./e2e",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3100",
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
  },
});
