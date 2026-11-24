# Sprint 4 — Isolated Groq Verification Runbook

Preparation only. Do not execute the live commands until the owner authorizes the first request.

## Isolation

Use a separate source copy and Compose project. Keep the primary stack on `fixture / fixture-v1`.
The isolated copy must use a unique `COMPOSE_PROJECT_NAME`, unused `WEB_PORT`, `API_PORT`, and
`N8N_PORT`, and fresh PostgreSQL, n8n, and file volumes. Never reuse the primary `.env`.

```sh
mktemp -d /tmp/creativeos-s4.XXXXXX
# Copy the repository into that directory, excluding .git, .env, .local, node_modules, .next and caches.
cd /path/to/isolated-copy
python3 scripts/init_env.py
# Edit only the isolated .env: unique project/ports; keep these until live approval:
# AI_PROVIDER=fixture, AI_MODEL=fixture-v1, FILE_PROVIDER=local
docker compose config --quiet
docker compose up -d --build --wait
python3 scripts/smoke.py
```

Confirm the resolved Compose project, ports, volume names, and container identities are unique before
startup. Do not run `docker compose down -v`; retain the isolated volumes for investigation.

## Synthetic fixture preparation

Create one fictional Morrow Orchard / Holiday Collection 2026 brief with no real client data. Use the
existing authorized API to submit and approve it, then record the project, brief, and snapshot IDs in
redacted evidence only. While still in fixture mode, verify the intended dependencies and queue state.

```sh
docker compose ps
# Authenticated API checks: approved snapshot; zero pending/running generations.
docker compose stop worker n8n
# Re-check zero pending/running jobs after both continuous consumers are stopped.
```

Do not enable live provider settings in the continuous worker. The one-shot runner is the only allowed
executor for the future live check.

## Authorized one-request sequence

Before every request, verify the same approved snapshot, exact stage inputs, zero pending/running jobs,
provider/model, request budget, and idempotency key. Submit one job, execute it once with the existing
runner, poll its persisted record, and stop on any unexpected request, timeout, duplicate, or state.

1. Brief Analyzer: one job; validate output, provider/model, status, attempt, tokens, latency.
2. Creative Strategist: require the completed analysis from step 1; inspect before continuing.
3. Select exactly one direction through the authorized API.
4. Content Planner: require that selected direction; request the synthetic target count once.
5. Select exactly one plan item through the authorized API.
6. Copywriting Assistant: use the selected content item and its current revision once.

The live configuration variable names are `AI_PROVIDER`, `AI_MODEL`, `AI_ENDPOINT`, and `AI_API_KEY`.
Set only in the isolated one-shot process/environment, never in the primary `.env` or continuous worker.
Use the approved HTTPS completion endpoint, restricted provider key, and bounded output/timeout settings.

For each job inspect `GET /api/v1/ai-generations/{id}` and record only redacted evidence: stage, IDs,
provider, model, prompt version, status, attempt, error code, input/output tokens, latency, and selected
proposal IDs. Never log raw keys, authorization headers, or raw client data.

## Restore and stop

After each authorized test, restore the isolated environment to `AI_PROVIDER=fixture` and
`AI_MODEL=fixture-v1`, restart only after confirming no live jobs remain, and verify the primary stack was
untouched. A provider timeout must be reconciled before any retry because it may still incur a charge.

```sh
# In the isolated copy only, after fixture restoration:
docker compose up -d --no-build --wait backend
docker compose ps
```

No live Groq request is part of this preparation checkpoint.
