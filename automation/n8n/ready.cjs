const { DatabaseSync } = require("node:sqlite");
const { readdirSync, readFileSync } = require("node:fs");
const { homedir } = require("node:os");
const { join } = require("node:path");

async function ready() {
  const res = await fetch("http://127.0.0.1:5678/healthz/readiness", {
    signal: AbortSignal.timeout(3000),
  });
  if (!res.ok) return false;
  const db = new DatabaseSync(
    join(process.env.N8N_USER_FOLDER || homedir(), ".n8n", "database.sqlite"),
    { readOnly: true },
  );
  try {
    const registered = db.prepare(
      "SELECT 1 FROM webhook_entity WHERE workflowId=? AND webhookPath=? AND method=?",
    );
    const dir = join(__dirname, "workflows");
    return readdirSync(dir).filter((file) => file.endsWith(".json")).every((file) => {
      const workflow = JSON.parse(readFileSync(join(dir, file), "utf8"));
      const trigger = workflow.nodes.find((n) => n.type === "n8n-nodes-base.webhook");
      return !!registered.get(workflow.id, trigger.parameters.path, trigger.parameters.httpMethod);
    });
  } finally {
    db.close();
  }
}
ready().then((ok) => process.exit(ok ? 0 : 1)).catch(() => process.exit(1));
