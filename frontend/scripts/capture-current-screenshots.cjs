/*
 * Read-only portfolio capture utility.
 * Run from frontend/ with: node scripts/capture-current-screenshots.cjs
 * Uses local synthetic demo accounts in memory; no storageState is written.
 */
const { chromium } = require("@playwright/test");
const fs = require("node:fs/promises");
const path = require("node:path");

const baseURL = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3100";
const outputDir = path.resolve(
  process.env.PORTFOLIO_SCREENSHOT_DIR || "../docs/screenshots/current",
);
const viewport = { width: 1440, height: 900 };
const force = process.argv.includes("--force");
const onlyArgument = process.argv.find((argument) => argument.startsWith("--only="));
const only = new Set(
  onlyArgument ? onlyArgument.slice("--only=".length).split(",").filter(Boolean) : [],
);
const results = { captured: [], skipped: [], failed: [] };

function selected(name) {
  return only.size === 0 || only.has(name);
}

async function hasVerifiedPng(name) {
  try {
    const handle = await fs.open(path.join(outputDir, `${name}.png`), "r");
    const signature = Buffer.alloc(8);
    await handle.read(signature, 0, signature.length, 0);
    await handle.close();
    return signature.equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]));
  } catch {
    return false;
  }
}

async function captureOne(name, route, operation) {
  if (!selected(name)) return;
  if (!force && await hasVerifiedPng(name)) {
    results.skipped.push({ name, route, reason: "verified file already exists" });
    console.log(`Skipped ${name}.png (already exists)`);
    return;
  }
  try {
    await operation();
    results.captured.push({ name, route });
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    results.failed.push({ name, route, reason });
    console.error(`Failed ${name} (${route}): ${reason}`);
  }
}

async function authenticate(context, role) {
  if (new URL(baseURL).hostname !== "localhost") throw new Error("Localhost required");
  const accounts = JSON.parse(await fs.readFile(path.resolve(__dirname, "../../.local/demo-accounts.json"), "utf8"));
  const email = role === "Agency Manager" ? "manager@example.com" : "lead@example.com";
  if (typeof accounts[email] !== "string") throw new Error("Missing synthetic credential");
  const page = await context.newPage();
  await page.goto(baseURL + "/login", { waitUntil: "domcontentloaded" });
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(accounts[email]);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL(/dashboard/);
  const me = await context.request.get(baseURL + "/api/v1/auth/me");
  if (!me.ok()) throw new Error(`${role} authentication was not detected (HTTP ${me.status()})`);
  await page.close();
}

async function getJSON(context, url) {
  const response = await context.request.get(baseURL + url);
  if (!response.ok()) throw new Error(`GET ${url} returned HTTP ${response.status()}`);
  return (await response.json()).data;
}

async function ids(context) {
  const projects = await getJSON(context, "/api/v1/projects?portal=agency&page_size=50");
  const briefs = await getJSON(context, "/api/v1/briefs?portal=agency&page=1");
  const brief = briefs.find((item) => item.title.includes("Aurora Vale") && item.status === "approved");
  const project = projects.find((item) => item.id === brief?.project_id);
  if (!project || !brief) throw new Error("No readable synthetic project or brief was found");
  const items = await getJSON(context, `/api/v1/projects/${project.id}/content-items`);
  return { projectId: project.id, briefId: brief.id, itemId: items[0]?.id };
}

async function capturePage(context, name, route, marker) {
  const page = await context.newPage();
  try {
    await page.goto(baseURL + route, { waitUntil: "networkidle" });
    if (new URL(page.url()).pathname === "/login") throw new Error("redirected to login");
    const text = await page.locator("body").innerText();
    if (/application error|internal server error|\bnot found\b/i.test(text)) throw new Error("error page");
    if (marker && !text.toLowerCase().includes(marker.toLowerCase())) {
      throw new Error(`expected marker \"${marker}\" was not visible`);
    }
    await page.screenshot({ path: path.join(outputDir, `${name}.png`), fullPage: true, animations: "disabled" });
    console.log(`Captured ${name}.png`);
  } finally {
    await page.close();
  }
}

async function captureStudio(context, briefId) {
  const page = await context.newPage();
  const route = `/admin/creative-studio?brief=${briefId}`;
  try {
    await page.goto(baseURL + route, { waitUntil: "networkidle" });
    if (new URL(page.url()).pathname === "/login") throw new Error("redirected to login");
    for (const [label, filename] of [
      ["Brief Analysis", "creative-studio-brief-analysis"],
      ["Creative Strategy", "creative-studio-creative-strategy"],
      ["Content Plan", "creative-studio-content-plan"],
      ["Copywriting", "creative-studio-copywriting"],
    ]) {
      await captureOne(filename, route, async () => {
        const tab = page.getByRole("navigation", { name: "Creative Studio stages" }).getByRole("button").filter({ hasText: label });
        await tab.click();
        await page.getByText(label, { exact: true }).first().waitFor();
        const text = await page.locator("body").innerText();
        if (/application error|internal server error|\bnot found\b/i.test(text)) throw new Error("error page");
        await page.screenshot({ path: path.join(outputDir, `${filename}.png`), fullPage: true, animations: "disabled" });
        console.log(`Captured ${filename}.png`);
      });
    }
  } finally {
    await page.close();
  }
}

async function captureAgency(context) {
  const data = await ids(context);
  const routes = [
    ["agency-dashboard", "/admin/dashboard", "Agency"],
    ["projects", "/admin/projects", "Projects"],
    ["project-detail", `/admin/projects/${data.projectId}`, "Project"],
    ["kanban-task-assignment", "/admin/tasks", "Tasks"],
    ["project-timeline", `/admin/projects/${data.projectId}`, "Project"],
    ["brief-management", "/admin/briefs", "Brief"],
    ["internal-approvals", `/admin/approvals${data.itemId ? `?item=${data.itemId}` : ""}`, "Approval"],
    ["agency-reports", "/admin/reports", "Report"],
    ["agency-notifications", "/admin/notifications", "Development inbox"],
    ["automation-monitoring", "/admin/automation", "Automation"],
    ["ai-evaluations", "/admin/evaluations", "Evaluation"],
    ["leads", "/admin/leads", "Lead"],
    ["clients", "/admin/clients", "Client"],
  ];
  for (const [name, route, marker] of routes) {
    await captureOne(name, route, () => capturePage(context, name, route, marker));
  }
  await captureStudio(context, data.briefId);
  return data;
}

async function captureClient(context) {
  const projects = await getJSON(context, "/api/v1/projects?portal=client&page_size=50");
  const project = projects[0];
  if (!project) throw new Error("No client-visible synthetic project was found");
  const itemData = await getJSON(context, `/api/v1/projects/${project.id}/content-items?portal=client`);
  const itemId = itemData[0]?.id;
  const routes = [
    ["client-dashboard", "/client/dashboard", "Projects"],
    ["client-projects", "/client/projects", "Projects"],
    ["client-project-detail", `/client/projects/${project.id}`, "Project"],
    ["client-approvals", `/client/approvals${itemId ? `?item=${itemId}` : ""}`, "Approval"],
    ["client-reports", "/client/reports", "Report"],
    ["client-notifications", "/client/notifications", "Client inbox"],
    ["attachment-management", "/client/files", "Files"],
  ];
  for (const [name, route, marker] of routes) {
    await captureOne(name, route, () => capturePage(context, name, route, marker));
  }
}

(async () => {
  await fs.mkdir(outputDir, { recursive: true });
  const browser = await chromium.launch({ headless: false });
  try {
    const agency = await browser.newContext({ viewport });
    await authenticate(agency, "Agency Manager");
    if (process.argv.includes("--smoke")) {
      await captureOne("agency-dashboard", "/admin/dashboard", () => capturePage(agency, "agency-dashboard", "/admin/dashboard", "Agency"));
      return;
    }
    await captureAgency(agency);
    await agency.close();

    const client = await browser.newContext({ viewport });
    await authenticate(client, "Client");
    await captureClient(client);
    await client.close();
  } finally {
    await browser.close();
  }
  console.log(`Capture summary: ${results.captured.length} captured, ${results.skipped.length} skipped, ${results.failed.length} failed.`);
  for (const failure of results.failed) console.log(`  FAILED ${failure.name} (${failure.route}): ${failure.reason}`);
  console.log(`Verified screenshots are in ${outputDir}`);
})().catch((error) => {
  console.error(`Capture stopped: ${error.message}`);
  process.exitCode = 1;
});
