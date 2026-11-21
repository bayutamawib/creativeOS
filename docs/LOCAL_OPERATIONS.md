# Operating the portfolio demo

## Service boundaries and configuration

Use the checked-in `compose.yaml` from the repository root. The [README](../README.md#run-locally) gives the startup commands. The [demo walkthrough](PORTFOLIO_DEMO.md) covers the seeded roles and the whole client journey. The migration service runs `alembic upgrade head` before FastAPI starts. Next.js proxies `/api/v1` on the browser origin. The backend uses an application database role. The worker polls durable generation jobs and outbox events with leases. The n8n bootstrap imports encrypted credentials and publishes nine repository workflow definitions. n8n sends HTTP callbacks to FastAPI. Neither a Python task runner inside n8n nor a cloud account is necessary. The [local n8n editor](http://localhost:5679) may ask you to create an owner to view the imported workflows. Editor setup is independent of execution. Keep owner credentials local.

The initializer supplies missing local secrets in `.env`. Keep database passwords and the n8n encryption key paired with their volumes. Avoid printing expanded Compose configuration. `docker compose config --quiet` validates it without expanding credentials to the terminal.

| Variable | Purpose |
|---|---|
| WEB_PORT, API_PORT, N8N_PORT | Loopback-only service ports. The web port determines the expected browser Origin |
| AGENCY_TIMEZONE | IANA timezone for calendar windows and schedules, default Asia/Jakarta |
| REMINDER_CRON, REPORT_CRON | Default reminder every minute and weekly report Monday at 09:00. Quote cron expressions in environment files |
| POSTGRES_PASSWORD, APP_DB_PASSWORD | Database bootstrap and application role secrets |
| WEBHOOK_KEY, WORKFLOW_KEY, FORMS_KEY | Webhook signing, n8n callback authentication and Forms receiver authentication |
| N8N_ENCRYPTION_KEY | Encrypts n8n credentials in its metadata volume |
| FILE_PROVIDER, DRIVE_ACCESS_TOKEN | Local files by default. Optional private Google Drive storage |
| AI_PROVIDER, AI_MODEL, AI_ENDPOINT, AI_API_KEY | Fixture by default. Compatible endpoint and provider-issued key for an explicitly authorized live test |
| AI_MAX_OUTPUT_TOKENS, AI_TIMEOUT_SECONDS | Per-request output cap and network timeout. Defaults are 2000 tokens and 15 seconds |

## Keep verification isolated

Use a separate copy of the delivered source for browser tests and screenshots. Copy source and workflow definitions, leaving local environment files, credentials, uploads and generated files in their original workspace. Run the initializer in the new copy to create fresh secrets. Before startup edit the three existing ports and add a unique Compose project name to the generated `.env`. For example, use `WEB_PORT=3310`, `API_PORT=8310`, `N8N_PORT=5879` and `COMPOSE_PROJECT_NAME=creativeos_portfolio` if those values are available. Keep `AI_PROVIDER=fixture`, `AI_MODEL=fixture-v1` and `FILE_PROVIDER=local`. Start, smoke-test and seed the copy with the README commands. The different project name gives the test stack separate volumes. Shut it down with `docker compose down` to retain those volumes.

## Integration readiness

| Integration | Status | Evidence and boundary |
|---|---|---|
| LLM fixture | Verified locally with a development adapter | The real worker persisted structured generations and draft summaries using `fixture-v1` |
| LLM HTTPS transport | Verified live for one synthetic copywriting generation | Groq, openai/gpt-oss-20b, attempt 1, structured output persisted. Fixture remains the demo default. Other live generation stages remain unverified. [CP7 evidence](IMPLEMENTATION_STATUS.md#cp7-controlled-groq-verification) |
| Local file storage | Verified locally with a development adapter | Project-scoped upload, validation, immutable references and authorized download |
| Google Drive | Implemented but not verified live | Private file adapter uses operator-supplied OAuth access token. Token renewal is manual |
| Notification inbox | Verified locally with a development adapter | Real n8n workflows call FastAPI to record per-recipient deliveries |
| Gmail | Unimplemented | The local recovery mailbox and notification inbox cover the demo |
| Telegram | Unimplemented | Notification deliveries in this release use the development inbox |
| Google Forms | Implemented but not verified live, receiver only | `POST /api/v1/integrations/google-forms/submissions` accepts authenticated, idempotent submissions. Upstream Forms forwarding is not implemented. The native inquiry form is exercised end to end |
| n8n | Verified locally | Actual event and schedule executions correlated with PostgreSQL. See the CP6 evidence |

## n8n JWT retention and production hardening

The standard JWT Webhook node in n8n 2.48.6 authenticates the request and copies its headers into the initial execution payload. n8n persists that payload before downstream nodes run. Redaction at the editor or downstream workflow nodes therefore leaves the initial SQLite write. Immediate pre-persistence header removal is unavailable through this setup’s supported save settings.

Compose disables saved success, error, progress and manual execution data and configures a one-minute sweep for marked payload rows. The webhook JWT expires after 30 seconds. FastAPI separately authenticates n8n callbacks and validates the signed event. n8n binds to loopback, and Docker, the metadata volume and backups require restricted operator access. CP6-A observed a bearer-bearing row immediately after execution **716**, then zero rows after pruning. PostgreSQL retained the correlated run and delivery evidence. n8n’s terminal journal could still independently confirm the execution. Pruning establishes removal from ordinary queries. A privileged reader could see a token before that sweep, and a backup or underlying SQLite pages can retain earlier bytes. [CP6-A evidence](IMPLEMENTATION_STATUS.md#cp6-final-integration-and-portfolio-demo)

Before a public deployment, require private orchestration networking, HTTPS and controlled editor access. Enforce authentication and strip authorization headers before anything persists the request. Use a supported trigger or a separately reviewed ingress that authenticates and forwards only the required signed envelope, with direct access to the trigger blocked. Re-test both successful and failed requests for immediate removal while retaining execution correlation. Store and rotate signing and callback credentials separately, minimize backup access and retention, and rehearse restore and incident response.

## Optional one-request live LLM check

CP7 verified Groq copywriting with 4096 tokens and a 30-second timeout. The adapter supplies `User-Agent: CreativeOS/1.0`, resolving the owner-diagnosed Cloudflare rejection. Use an isolated stack, stop its continuous worker and n8n, drain the queue and execute only the intended job once. Restore fixture mode afterward. A timeout requires reconciliation before another attempt.

The default demo uses fixture mode. For a future authorized test, select any provider accepting HTTPS Chat Completions, bearer authentication, JSON-object responses, temperature and max_tokens. Supply the full HTTPS completion URL in `AI_ENDPOINT`, the provider’s exact model ID in `AI_MODEL` and a restricted key in `AI_API_KEY`. The adapter expects Chat Completions-style `choices[0].message.content` with a JSON object. The provider is operator-selected. Keep the normal worker on `fixture / fixture-v1`. Switching a running worker to live mode can send approved brief snapshots automatically.

Use one synthetic metrics input in an isolated one-off backend process. It makes at most one adapter request, never publishes or writes a report, and does not retry. From the root, the following exercises the example in fixture mode first.

```sh
docker compose run --rm -T --no-deps -e AI_PROVIDER=fixture -e AI_MODEL=fixture-v1 backend python - < scripts/check_summary.py
```

Only after approving the provider, privacy policy and potential charge, load `AI_ENDPOINT`, `AI_MODEL` and `AI_API_KEY` into the calling shell through a local secret manager. The command passes the variable names. Keep keys out of Git, screenshots, shell history and chat.

```sh
docker compose run --rm -T --no-deps \
  -e AI_PROVIDER=compatible -e AI_ENDPOINT -e AI_MODEL -e AI_API_KEY \
  -e AI_MAX_OUTPUT_TOKENS=256 -e AI_TIMEOUT_SECONDS=15 \
  backend python - < scripts/check_summary.py
```

The example uses one completed, two open and zero overdue tasks. Expect an `executive_summary` string and four arrays named `completed_work`, `pending_activities`, `risks` and `recommended_next_actions`. The validator checks the schema and every sentence against the allowed evidence statements. A provider can return structurally valid JSON and still fail grounding. The script reports only safe failure codes. Check `missing_credentials` and `invalid_provider_configuration` locally. Investigate `provider_http_error`, `provider_rate_limit` or `provider_unavailable` before another attempt. `invalid_output` and `unsupported_report_claim` require inspecting the contract. Network timeouts can still incur a provider charge. Use a provider-side budget and keep all customer data out of this check.

## Reproduce the CP6-A checks

With a healthy, seeded test stack, run the spec and secret checks and then the PostgreSQL suite from the root. The backend runner creates its own temporary database.

```sh
python3 scripts/check_specs.py
python3 scripts/check_secrets.py
python3 scripts/smoke.py
sh scripts/test_backend.sh
```

From `frontend/`, with Node 24 and the browser installed, run the frontend checks and the full browser suite. The two flags exercise queue recovery by stopping and starting the test worker.

```sh
npm ci
npm run lint
npm run typecheck
npm test
npm run build
npx playwright install chromium
CP3_TEST_WORKER_RESTART=1 CP4_TEST_WORKER_RESTART=1 npm run test:e2e
```

Use the isolated stack’s web origin in `PLAYWRIGHT_BASE_URL` when it differs from port 3100. See the [verification record](IMPLEMENTATION_STATUS.md#cp6-final-integration-and-portfolio-demo) for observed outputs and execution IDs.

## Workflow evidence and troubleshooting

- **Startup or port conflict.** Run `docker compose ps -a` and `docker compose logs --tail=40 migrate`. Allow time for the first n8n import and nine publications. Change ports in `.env` if occupied, then rerun `docker compose up -d --wait`. Use `python3 scripts/smoke.py` to check liveness, database readiness, authentication rejection and both HTTP surfaces. If the worker stayed in `Created` after a failed bootstrap, wait for n8n to be healthy and run `docker compose up -d --no-build --wait worker`.
- **Login or CSRF failure.** Use the configured localhost origin, including its port. Read the generated account file locally. A 429 means wait for the next minute. For lost access, the development recovery mailbox is private to the backend container at `/home/creative/.local/mail/`. A recreated backend clears that mailbox.
- **Empty client pages.** Check active membership and organization, client-visible milestones, release state and report publication. A binding decision needs a Client Admin or an active delegate for that exact project. Refresh after another person has changed a revision.
- **Pending or uncertain work.** Inspect **Automation** as a Manager or Admin. Follow an event ID through attempts, runs, the consumer receipt and deliveries. Check worker health. Only retry eligible transient failures using the supported UI. An uncertain external delivery would require reconciliation before replay.
- **Independently check n8n.** From the root run `python3 scripts/verify_workflow.py lead.created <lead-uuid>` or `python3 scripts/verify_workflow.py report.published <report-uuid>`. For exact revisions add `--revision <revision-uuid>` to content-event checks. The verifier matches PostgreSQL to the real workflow ID, execution ID and terminal state in n8n. n8n's rotated terminal journal provides short-lived independent evidence after payload pruning. PostgreSQL retains the business correlation.
- **Reproduce both schedules quickly.** In a separate working copy with a new Compose project name, fresh keys and three unused ports, set both cron expressions to `"* * * * *"` before startup. Seed and run the full browser suite there. A planning, in-progress or in-review project is eligible for last week's report. Query `scheduled_reports.report_id` and run `python3 scripts/verify_workflow.py report.schedule <report-uuid>`. Resume normal weekly timing on the regular demo stack.
- **Backup and restore.** Treat database dumps, uploads, encrypted metadata and keys as private. Stop writes for a coordinated backup. Use `umask 077` and `docker compose exec -T postgres pg_dump -U postgres -Fc creativeos > /private/path/creativeos.dump`. Back up the file and stopped n8n volumes with owner/permissions preserved. Keep `.env` and encryption keys separately protected. Restore into a distinct project with fresh volumes: bootstrap its database roles, restore the dump into an empty database owned by the application role using `pg_restore --exit-on-error`, restore the matching files, metadata and keys, then migrate and smoke-test. Rehearse backup restoration before production use.
