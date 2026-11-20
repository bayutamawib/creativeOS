#!/bin/sh
set -eu
umask 077
credentials=$(mktemp)
trap 'rm -f "$credentials"' EXIT
node /creative/credentials.cjs "$credentials"
n8n import:credentials --input="$credentials"
rm -f "$credentials"
n8n import:workflow --separate --input=/creative/workflows
for workflow in /creative/workflows/*.json; do
  workflow_id=$(node -p 'require(process.argv[1]).id' "$workflow")
  n8n publish:workflow --id="$workflow_id"
done
unset WEBHOOK_KEY WORKFLOW_KEY
exec /docker-entrypoint.sh start
