import { expect, test } from "@playwright/test";
import { sign } from "./accounts";

test("keyboard errors, workspace bypass link and responsive portals", async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  const response = await page.goto("/login");
  const button = page.getByRole("button", { name: "Sign in" });
  await expect(button).toHaveCSS("transition-property", "none");
  const contrast = await button.evaluate((element) => {
    const style = getComputedStyle(element);
    function luminance(color: string) {
      const [r, g, b] = color
        .match(/[\d.]+/g)!
        .slice(0, 3)
        .map(Number)
        .map((v) => v / 255)
        .map((v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    }
    return (
      (luminance(style.color) + 0.05) /
      (luminance(style.backgroundColor) + 0.05)
    );
  });
  expect(contrast).toBeGreaterThanOrEqual(4.5);
  console.log("Sign-in button contrast", contrast.toFixed(2));
  expect(response?.headers()["referrer-policy"]).toBe("no-referrer");
  expect(response?.headers()["x-frame-options"]).toBe("DENY");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await page.getByLabel("Email address").focus();
  await page.keyboard.type("unknown@example.invalid");
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Password", { exact: true })).toBeFocused();
  await page.keyboard.type("invalid demo input");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("alert")).toBeVisible();
  for (const [name, portal, routes] of [
    [
      "manager",
      "admin",
      ["dashboard", "reports", "approvals", "automation", "evaluations"],
    ],
    [
      "lead",
      "client",
      ["dashboard", "briefs", "reports", "approvals", "files"],
    ],
  ] as const) {
    await sign(page, name);
    for (const route of routes) {
      await page.goto("/" + portal + "/" + route);
      if (route === "dashboard") {
        const timing = await page.evaluate(() => {
          const entry = performance.getEntriesByType(
            "navigation",
          )[0] as PerformanceNavigationTiming;
          return {
            response_ms: Math.round(entry.responseEnd),
            dom_ms: Math.round(entry.domContentLoadedEventEnd),
            html_bytes: entry.encodedBodySize,
          };
        });
        console.log(portal, "local dashboard navigation", timing);
      }
      await page.keyboard.press("Tab");
      await expect(
        page.getByRole("link", { name: "Skip to content" }),
      ).toBeFocused();
      await expect(
        page.getByRole("link", { name: "Skip to content" }),
      ).toHaveCSS("outline-style", "solid");
      await page.keyboard.press("Enter");
      await expect(page.locator("#workspace-content")).toBeFocused();
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth),
        route,
      ).toBeLessThanOrEqual(375);
    }
    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/login/);
  }
  const timing = await page.evaluate(() => {
    const n = performance.getEntriesByType(
      "navigation",
    )[0] as PerformanceNavigationTiming;
    return {
      dom_ms: Math.round(n.domContentLoadedEventEnd),
      response_ms: Math.round(n.responseEnd),
    };
  });
  console.log("Local mobile login navigation", timing);
});
