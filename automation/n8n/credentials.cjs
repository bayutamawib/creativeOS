const fs = require("node:fs");
const crypto = require("node:crypto");

const signingKey = crypto
  .createHmac("sha256", process.env.WEBHOOK_KEY)
  .update("webhook-jwt-v1")
  .digest("hex");
const credentials = [
  {
    id: "creativeJwtAuth01",
    name: "Creative signed dispatcher",
    type: "jwtAuth",
    data: { keyType: "passphrase", algorithm: "HS256", secret: signingKey },
  },
  {
    id: "creativeCallback1",
    name: "Creative workflow callbacks",
    type: "httpHeaderAuth",
    data: { name: "X-Creative-Service", value: process.env.WORKFLOW_KEY },
  },
];
fs.writeFileSync(process.argv[2], JSON.stringify(credentials), { mode: 0o600 });
