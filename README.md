# CREATIVE OS

## Run locally

Install Docker Compose and Python 3. From the repository root run:

```sh
python3 scripts/init_env.py
docker compose up -d --build --wait
python3 scripts/smoke.py
python3 scripts/seed_local.py
```

Open the workspace at http://localhost:3100. FastAPI serves liveness and database readiness at http://localhost:8100/health/live and http://localhost:8100/health/ready. The local n8n editor is at http://localhost:5679. Set up its owner account on first use. The three published ports can be changed in the generated `.env`. Keep this file with the persistent data volumes.

PostgreSQL starts before a one-shot Alembic migration. The API and worker wait for that migration. Worker health measures a recent successful database heartbeat. The worker claims committed lead and task-assignment events, retries unconfirmed deliveries, and records the result. n8n keeps its own metadata in a separate volume. Use `docker compose down` to stop the stack and retain its data.

## Sign in

Open [the local sign-in page](http://localhost:3100/login). Use localhost for the browser origin. The credentials file `.local/demo-accounts.json` is generated with owner-only permissions and excluded from Git. Repeat seeding preserves existing credentials, roles and client decisions.

| Seed identity | Portal and access |
|---|---|
| admin@example.com | Agency Admin |
| manager@example.com | Agency Manager with Team Member administration |
| producer@example.com | Agency Team Member |
| lead@example.com / reviewer@example.com | Northline Studio client admin / member |
| publisher@example.com / editor@example.com | Clover Press client admin / member |

An agency manager can invite a Team Member from the agency workspace. The inviter receives a private single-use link for manual delivery. Existing account holders sign in before accepting. A client admin can grant or revoke authority from a project in the client workspace. The member’s review access updates on the next request. Deliverable review opens in CP4.

Password recovery uses a local development mailbox in the backend container. Inspect the newest message in `/home/creative/.local/mail/` using `docker compose exec backend sh`. Open its reset URL before the 20-minute expiry. Replacing the development container clears that mailbox. Authenticated sessions, authorization history and token digests reside in PostgreSQL. No external email service is configured.

## Checks

```sh
python3 scripts/check_specs.py
sh scripts/test_backend.sh
cd frontend
npm ci
npm run lint
npm run typecheck
npm test
```

The backend test command applies migrations to a fresh temporary PostgreSQL database and removes that test database at exit. CI also builds the production frontend as part of the Compose startup.


## Browser verification

The Playwright suite uses the seeded local users. From `frontend/`, run `PLAYWRIGHT_CHANNEL=chrome npm run test:e2e` with Google Chrome installed. CI installs Playwright Chromium and runs `npm run test:e2e`. If you change WEB_PORT, set PLAYWRIGHT_BASE_URL to the matching localhost URL. The delegation test uses two independent browser sessions and restores the seeded member’s default access.

## Operations checkpoint

Submit a native inquiry at [Start a project](http://localhost:3100/inquiry). In the Agency workspace, open Leads, select the inquiry, qualify it and convert it. Enter an initial project name to create that project in the conversion transaction. Issue the contact a private invitation link. The contact can accept the invitation, sign in and open their organization's projects.

Use Projects to manage project dates, milestones, the project team and tasks. Team Members see their assigned projects and tasks. Clients see released milestones and their completion percentage. Archiving removes a project from the operational portals and retains its history.

The Compose n8n bootstrap imports and publishes all four checked-in webhook definitions for WF-A, WF-B and WF-C. Each workflow uses HTTP-based orchestration. The worker signs its envelope and sends a short-lived bearer token. n8n uses its encrypted callback credential to call FastAPI. Local deliveries appear under the recipient's **Inbox**. The development inbox requires development mode. External Google Forms, Telegram and email services require separate live setup.

Run the browser suite against the seeded Compose stack to generate and verify both workflows. The operations tests match the exact resource's outbox event, completed run, delivery receipt and recipient rows to the successful execution in n8n's own metadata. To recheck either event from the repository root run one of the following commands with its lead or task UUID.

```sh
python3 scripts/verify_workflow.py lead.created <lead-uuid>
python3 scripts/verify_workflow.py task.assigned <task-uuid>
```

When upgrading an existing CP1 workspace, run `python3 scripts/init_env.py` before Compose to generate the missing integration keys and retain existing credentials. After editing a workflow definition, restart n8n to import and publish the repository version.


## Creative Intelligence

Open **Briefs** in the client portal to upload references, save a draft and submit it as a client admin. The agency reviewer can request clarification or approve the displayed version. Approval history retains the submitted fields and reference hashes. Shared attachments appear in **Files**. Downloads always go through FastAPI.

Open **Creative Studio** from an approved agency brief. The approved snapshot starts analysis and strategy. Select a direction to start planning. Select a plan item to create its two project tasks. **Create draft deliverable** saves the internal draft. **Suggest copy** generates a proposal and **Save copy as revision** creates the next immutable revision.

### Local and external adapters

Compose defaults to deterministic AI fixtures, a private local file volume and development inbox notifications. Local uploads support UTF-8 TXT and validated, re-encoded PNG/JPEG images up to 5 MiB. Downloads check the stored hash. Back up the `creative_files` volume with the PostgreSQL data. Reference documents contribute metadata and hashes to AI input. Brand guidance supplied through the agency brand-guidelines endpoint is captured as text.

The optional Drive adapter uses `FILE_PROVIDER=google_drive` and a dedicated account's `DRIVE_ACCESS_TOKEN`. The backend creates private files under opaque names and stores their provider IDs internally. The operator supplies and refreshes the OAuth access token. Existing local files continue to use local storage. Live Drive access has not been verified. [Google Drive upload documentation](https://developers.google.com/workspace/drive/api/guides/manage-uploads)

The optional LLM adapter accepts a Chat Completions-compatible HTTPS endpoint in `AI_ENDPOINT`, an operator-selected `AI_MODEL`, and `AI_API_KEY` when `AI_PROVIDER=compatible`. The API and worker must use the same configuration. Keep credentials in the ignored environment file or deployment secret store. `AI_TIMEOUT_SECONDS` and `AI_MAX_OUTPUT_TOKENS` bound individual requests. Brief approval can start generation automatically, so use fixture mode for local tests. Live LLM calls require separate authorization.

### Workflow verification

The creative browser test matches the exact brief and selected direction to PostgreSQL events, receipt, notifications and completed snapshot-bound jobs. It checks the workflow ID and successful execution independently inside n8n. To verify existing results locally, run either command with its resource UUID.

```sh
python3 scripts/verify_workflow.py brief.approved <brief-uuid>
python3 scripts/verify_workflow.py creative_direction.approved <direction-proposal-uuid>
```

From `frontend/`, running `CP3_TEST_WORKER_RESTART=1 PLAYWRIGHT_CHANNEL=chrome npm run test:e2e -- studio.spec.ts` also stops the local worker, queues one job, restarts the worker and waits for the same job to complete.
