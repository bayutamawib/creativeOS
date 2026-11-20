#!/bin/sh
set -eu
umask 077
credentials=$(mktemp)
trap 'rm -f "$credentials"' EXIT
node /creative/credentials.cjs "$credentials"
n8n import:credentials --input="$credentials"
rm -f "$credentials"
definitions=$(mktemp -d)
cp /creative/workflows/*.json "$definitions/"
node -e 'const fs=require("node:fs"),p=process.argv[1],w=JSON.parse(fs.readFileSync(p));w.nodes[0].parameters.rule.interval[0].expression=process.env.REMINDER_CRON || "0 9 * * *";fs.writeFileSync(p,JSON.stringify(w))' "$definitions/deadline-schedule.json"
n8n import:workflow --separate --input="$definitions"
rm -r "$definitions"
for workflow in /creative/workflows/*.json; do
  workflow_id=$(node -p 'require(process.argv[1]).id' "$workflow")
  n8n publish:workflow --id="$workflow_id"
done
unset WEBHOOK_KEY WORKFLOW_KEY
exec /docker-entrypoint.sh start
