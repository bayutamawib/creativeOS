# CREATIVE OS — Implementation status

## CP3 Creative Intelligence

**CP3 VERIFIED on the local stack.** CP3-A passed before CP3-B began. The five Compose services are healthy. CP4 awaits checkpoint review and explicit authorization.

### Preflight and CP3-A · VERIFIED

Initialized the local repository and committed CP2 as `b35d773`. Audited all 148 staged paths, compared staged bytes with generated credentials, scanned common secret formats and inspected both reference images. Environment files, local credentials, assistant settings, dependency caches, uploads and database artifacts are excluded. No remote was configured. Existing volumes were retained.

Migration `0006_briefs` adds files, attachment links, versioned briefs, immutable snapshots and brand guidelines. New FastAPI services and Next.js brief workspaces provide project-scoped uploads, downloads, drafting, clarification, submission and agency review. Approval commits the exact brief, brand context, attachment hashes, audit and pending outbox event together. During CP3-A the dispatcher claims its registered event types only.

On a separate PostgreSQL 16 cluster, `alembic upgrade head`, `alembic check`, Ruff, strict mypy and `pytest -q` passed (31 tests). The strengthened snapshot mutation test and brief suite also passed separately. The browser exercised upload, attachment selection, client submission and agency approval. All seven Chrome journeys passed against Compose. Frontend ESLint, TypeScript and both Vitest tests passed. A first Compose migration invocation inherited the test database password and failed authentication before writing. Running Compose with its own environment applied the migration and all five services became healthy.

### CP3-B · VERIFIED

Approved brief snapshots drive the Brief Analyzer and Creative Strategist. An agency decision starts the Content Planner. Selecting a plan item creates its template tasks once. The selected item can become an internal draft. The Copywriting Assistant proposes changes to the exact current revision, and a human saves the next revision. The Report Summarizer has a typed metrics interface and adapters for CP5. FastAPI owns decisions, durable job states, revision creation, audits and notification receipts. The existing worker executes Python. Both new n8n workflows use authenticated HTTP.

| Command or gate | Observed result |
|---|---|
| `docker compose config --quiet`, `docker compose up -d --build --wait` | Production frontend and backend images built. The seeded CP2 database was upgraded in place through `0006_briefs`, `0007_studio` and `0008_file_provider_ref`. Existing PostgreSQL and n8n volumes were preserved. |
| `sh scripts/test_backend.sh` | Ruff passed, strict mypy passed for 48 modules, all migrations applied to a fresh PostgreSQL database, and Alembic detected no drift. **42 tests passed** in 29.07 seconds with one upstream Starlette TestClient deprecation warning. The host PostgreSQL 16 run also passed all 42 tests. |
| `cd frontend && npm run lint && npm run typecheck && npm test` | ESLint and TypeScript passed. Both Vitest tests passed. |
| `CP3_TEST_WORKER_RESTART=1 PLAYWRIGHT_CHANNEL=chrome npm run test:e2e` in `frontend/` | All eight Chrome journeys passed in 46.2 seconds. They exercised client files and history, agency approval, generated directions, human selection, project tasks, copy suggestions and saving revision 2. With the worker stopped, the browser queued job `3006621d-8ec2-435c-b3b5-2f4238db3f42`. After the worker restarted, that job completed. |
| `python3 scripts/verify_workflow.py` from the browser journeys | Each check joined the exact resource, delivered event, completed run, processing receipt and recipient rows, then compared the workflow ID and success status against n8n's independent execution database. The creative checks also matched approved snapshot IDs, job types and service identity. |
| `python3 scripts/smoke.py`, `python3 scripts/check_specs.py`, `git diff --check` | Local HTTP smoke tests passed. The specification check passed nine references, 21 JSON examples, workflow and database coverage, and 108 RBAC expectations. Diff whitespace checks passed. |

| Event | PostgreSQL event UUID | Successful n8n execution | Development inbox deliveries |
|---|---|---:|---:|
| Brief approved, analysis and strategy completed | `61cbce9b-8821-4544-baa7-cd29695c09a6` | **22** | 2 |
| Direction approved, plan completed | `a6f0fa7f-8e2f-4397-9bc0-5e03572a0a90` | **23** | 2 |
| Lead created, CP2 regression | `4984ecf9-c335-47b2-8f05-ed93d29c7150` | **20** | 2 |
| Task assigned, CP2 regression | `db6335a5-6d8b-4810-9b98-182bc578008a` | **21** | 1 |

**Security and recovery.** PostgreSQL/API tests cover foreign-tenant and unassigned-project denials, internal file and draft visibility, unsafe names and content, oversized files, image sanitization, legacy file reads and hash mismatches. They also cover concurrent approval, snapshot mutation rejection, duplicate job admission, stale input cancellation, revoked assignments, workflow stage and attempt scoping, human selection, deduplicated task/draft writes, missing credentials, malformed output, retry exhaustion and late worker completion after lease takeover. CP1 session, CSRF and delegated-role tests and CP2 operations tests also passed. Provider transport error cases used controlled responses.

Execution 22 produced fixture jobs `51211c2f-8155-4280-96e8-39b1cdfbf380` and `4a3d6466-c02a-40f1-b31b-99e42df0d037`. Execution 23 produced `4897b4f9-17ac-43c7-a2f9-5b90d0d541f9`. An earlier browser run passed the six CP1/CP2 journeys and stopped the two creative tests during setup because Compose ran from the frontend directory. The test helper now invokes Compose from the repository root. A strict mypy finding in the optional Drive response reader was also corrected.

### CP3 file inventory

| Area | Created or modified |
|---|---|
| Persistence and APIs | `backend/alembic/env.py`, revisions `0006_briefs_briefs.py`, `0007_studio_studio.py`, `0008_file_provider_ref.py`, `backend/app/{ai_models,brief_models,brief_inputs,models,project_models,config,main}.py`, `api/{briefs,studio,inbox,workflows}.py` |
| Services and runtime | `backend/app/ai/{__init__,contracts,providers,reporting,runner}.py`, `services/{assets,drive,briefs,creative_workflow,studio,workflows}.py`, `worker.py`, `backend/Dockerfile`, `backend/requirements.txt`, `compose.yaml`, `.env.example`, n8n `workflows/{brief-approved,direction-approved}.json` |
| Portals | Admin and client layouts and brief pages, admin Creative Studio and notifications, client Files and new brief routes, `frontend/components/{brief-page,brief-workspace,creative-studio}.tsx`, `frontend/lib/{briefs,browser-api,studio}.ts` |
| Verification and documentation | `backend/tests/{conftest,test_briefs,test_studio}.py`, `frontend/e2e/{accounts.ts,briefs.spec.ts,studio.spec.ts}`, `scripts/verify_workflow.py`, `README.md`, `docs/DECISIONS.md` and this report. The preflight ignore rules are in the CP2 baseline. |

**Integration limits.** All successful creative generations used the deterministic `fixture-v1` model. The compatible HTTPS adapter and Drive request/response handling have local tests. Live LLM, Drive, Gmail and Telegram delivery are unverified. The running stack used local file storage and the development inbox. Drive requires an operator-renewed OAuth access token. A storage process crash before the metadata commit can leave unreferenced private bytes. Uploaded references contribute metadata and checksums to AI context. Automatic file text extraction is outside this implementation. Client deliverable approvals belong to CP4 and reporting integration to CP5.

## CP2 Operations · 20 November 2026

**CP2 VERIFIED.** CP2-A passed before CP2-B began. Both operations workflows ran in local n8n and produced verified development inbox deliveries. The stack is ready for checkpoint review. CP3 awaits explicit authorization.

### CP2-A · VERIFIED

A browser submitted an inquiry, a manager qualified and converted it, issued a single-use client invitation, and the new client signed in and saw the initial project. Conversion locks the lead and commits the client, optional project, lead link and audit together. The separate registration action reuses CP1 account and session checks. An authenticated alternative Google Forms intake API deduplicates by submission ID and fingerprint.

Changed files include the 0004 intake migration, operations models, intake inputs, services and API routers, auth registration, worker, config, Compose, environment initializer, n8n bootstrap/credentials scripts and WF-A JSON. Frontend additions include the inquiry route, agency leads list/detail, lead actions and client directory. Added PostgreSQL intake/outbox tests and an onboarding browser test.

- `docker compose up -d --build` (targeted backend, worker and frontend builds) applied 0004 over the seeded CP1 database. All five services became healthy. WF-A was imported and published on the local n8n instance.
- A real HTTP inquiry produced lead `99351752-f5de-4d6a-9124-5bc1faea0068`. PostgreSQL showed delivered on attempt 1, a completed run and two delivered development-inbox records. A separate read of n8n execution metadata showed execution `1`, workflow `creativeLeadWf01`, status `success`.
- `ruff check`, strict `mypy` and `alembic check` passed. `pytest -q` passed 22 tests on a separate PostgreSQL 16 cluster. Coverage includes overlapping conversions/redemptions, authorization, rollback, expired claims, lost acknowledgment, duplicate steps and isolated recipient deliveries. One existing Starlette TestClient deprecation warning.
- `npm run lint`, `npm run typecheck`, and `npm test` passed (2 Vitest cases). `PLAYWRIGHT_CHANNEL=chrome npm run test:e2e` passed all 5 Chrome journeys against Compose, including the new onboarding path.
- Notifications used a transactional development inbox. Google Forms, Telegram and email provider delivery were not exercised live. Client invitation links are shared manually by the authorized operator. CP2-B may now proceed.

### CP2-B · VERIFIED

The agency workspace now supports project search, creation, editing and archival, project teams, internal tasks with multiple assignees, task status and deadline changes, and explicit milestone release. Clients can switch authorized organizations, open a project and see its released milestones. FastAPI scopes detail, list, progress and notification queries. Managers can review client memberships and revoke unused invitations. Significant operations write audit entries in the same transaction.

| Gate or command | Observed result |
|---|---|
| `docker compose config --quiet`, `docker compose up -d --build --wait`, `python3 scripts/smoke.py` | Configuration validated, both application images built, migration exited successfully and all five services became healthy. HTTP liveness, migrated database readiness, frontend and n8n checks passed. |
| `sh scripts/test_backend.sh` | Ruff passed, strict mypy passed across 33 application modules, clean PostgreSQL migration to `0005_projects` passed, and Alembic reported no schema drift. **29 tests passed** with one existing Starlette TestClient deprecation warning. Includes the 16 CP1 authentication, session, role and client-isolation regression cases. |
| Project and task behavior | PostgreSQL and API tests exercised project CRUD/archival, dual-role portal scope, foreign organization denial, concurrent assignment, compound ownership constraints, released milestone aggregation, task lifecycle and deadline validation, removal of assignment-derived access, stale claims and recipient-specific notification deduplication. |
| `npm run lint`, `npm run typecheck`, `npm test` in `frontend/` | ESLint, Next route types and TypeScript passed. **2 Vitest tests passed**. |
| `PLAYWRIGHT_CHANNEL=chrome npm run test:e2e` | **6 Chrome journeys passed** on the running Compose stack. The operations journeys include public onboarding, agency project and task management, an assignee's inbox and status update, client milestone visibility, and project archival. Two earlier browser attempts found ambiguous navigation or text selectors. The final suite waits for the intended page and asserts visible content. |
| `python3 scripts/verify_workflow.py` invoked by both operations browser tests | WF-A event `f2a99779-b376-482d-b79e-1c71bb87a1c5` matched successful n8n execution **8** and **2** development inbox deliveries. WF-C event `f2d83d0b-9945-4c71-9bb8-3bb24b54b1aa` matched execution **9** and **1** delivery. Each check matched the specific resource, delivered outbox event, completed run, logical step receipt and delivered notification rows to n8n's independent execution database. Unsigned HTTP POSTs to both production webhook paths returned 401. |
| `python3 scripts/check_specs.py` | Passed all nine specification references, 21 JSON examples, workflow and database checks and 108 RBAC matrix expectations. |

A separate ephemeral n8n instance started with an empty metadata directory and the repository bootstrap. It imported two encrypted credentials, published both workflows and registered both production webhook paths. An initial check at editor readiness ran before registration finished. The Compose n8n health check now also reads the expected webhook registrations. After recreating n8n with that health check, all five Compose services were healthy and the complete Chrome suite passed again (6 cases, 33.6 seconds). For WF-A, execution **10** matched event `913359bd-a98c-473d-9cd0-51c019aee05c` and two delivered notifications. For WF-C, execution **11** matched event `f44d9951-c4ee-410a-817d-d1149e289b5a` and one delivered notification.

### CP2 file inventory

- **Database and services** — `backend/alembic/env.py`, revisions `0004_operations_intake.py` and `0005_projects_projects.py`, `backend/app/models.py`, `operations_models.py`, `project_models.py`, `intake_inputs.py`, `project_inputs.py`, `config.py`, `main.py`, `worker.py`, `services/{agency,clients,intake,projects,tasks,workflows}.py`, `api/{auth,inbox,intake,projects,workflows}.py`, and `backend/requirements.txt`.
- **Workflow and runtime** — `compose.yaml`, `.env.example`, `scripts/init_env.py`, `automation/n8n/bootstrap.sh`, `credentials.cjs`, `ready.cjs`, and `workflows/{lead-created,task-assigned}.json`. Workflow definitions contain references to encrypted credentials. The Python worker and FastAPI perform all business writes.
- **Web app** — Public inquiry/sign-in pages, portal layouts, agency leads, clients, projects, tasks and notifications pages, client project list/detail, shared styles, `components/{inquiry,lead-actions,client-invite,list-filters,operation-form,project-controls,project-list}.tsx`, and `lib/{server-api,intake,projects}.ts`.
- **Evidence and documentation** — `backend/tests/test_{intake,outbox,projects}.py`, `frontend/e2e/{intake,projects}.spec.ts`, `scripts/verify_workflow.py`, `README.md`, this report, and ADR-017 through ADR-021 in `docs/DECISIONS.md`.

**Verification limits.** Google Forms intake was exercised at the authenticated API boundary using synthetic submissions. Telegram, Gmail and a live Google Form were not connected. Notifications in this checkpoint were delivered to the development inbox. The browser suite creates synthetic business records in the local demo database. The project has no Git working tree. No commit, push or deployment was performed.

## CP1 Foundation · 20 November 2026

**CP1 VERIFIED. CP1-A and CP1-B passed their local acceptance gates in order.** The seeded Compose stack is running. No outstanding checkpoint blockers. CP2 Operations awaits explicit authorization.

### CP1-A implementation

- Added `compose.yaml`, `.env.example`, `.gitignore`, `infra/init-db.sh`, both Dockerfiles and build-context exclusions. Local secrets are generated once with owner-only file permissions. The frontend, backend and n8n have loopback listeners.
- Added `backend/app/`, Alembic configuration and the baseline revision in `backend/alembic/`, locked runtime/test dependencies, Ruff, mypy and live API/database tests in `backend/tests/`.
- Added a Next.js App Router shell with separate admin and client layouts, local Inter fonts, Tailwind tokens, a shadcn/ui button and a server-side FastAPI readiness indicator. Frontend dependencies are locked. Vitest covers connection status. Playwright exercises navigation against the running system.
- Added `.github/workflows/ci.yml`, local setup in `README.md` and the environment, smoke and isolated PostgreSQL test commands in `scripts/`.

### CP1-A checks

- `python3 scripts/check_specs.py` passed the CP0 contract checks. `docker compose config --quiet` validated the configuration.
- `docker compose build backend frontend` built both images. `sh scripts/test_backend.sh` applied the migration on a separate newly created PostgreSQL database, passed Ruff and strict mypy, and passed 2 Pytest cases. The test database was removed by the runner. Starlette emitted one deprecation warning about its HTTPX test client adapter.
- `npm run lint`, `npm run typecheck` and `npm test` passed in `frontend/` (2 Vitest cases). `PLAYWRIGHT_CHANNEL=chrome npm run test:e2e` passed the browser case for both portals and their live backend connection. The first browser attempt raced a container recreation and received connection refused. The passing run used the ready frontend.

- After correcting the initial n8n cold-start grace period, `docker compose up -d --no-build --wait` exited 0. All five long-running services reported healthy. The one-shot migration exited 0. `python3 scripts/smoke.py` passed and the n8n editor returned HTTP 200. n8n reported its optional internal Python task runner unavailable. The application worker runs in the backend image.

### CP1-B implementation

| Area | Files created or modified | Delivered behavior |
|---|---|---|
| Database and runtime | `backend/app/models.py`, `db.py`, `config.py`, `alembic/env.py`, revisions `0002_identity.py` and `0003_recovery.py`, requirements and Compose | Users, both membership types, project ownership roots, project-scoped grants, audit, invitations, sessions, reset tokens and public-auth rate counters. Grants retain history and same-client FK constraints. |
| Authentication | `backend/app/security.py`, `schemas.py`, `main.py`, `api/deps.py`, `api/auth.py`, `services/sessions.py`, `recovery.py`, `rate_limit.py` | Argon2id, login/me/refresh/logout, guarded invitation redemption, password recovery via a private dev mailbox, secure cookies, expiry, token rotation, Origin and CSRF checks, safe validation errors. |
| RBAC and isolation | `backend/app/api/{agency,clients}.py`, `backend/app/services/{agency,clients}.py` | Scoped roster and membership actions, last-Admin serialization, non-security operational settings, active client checks, project delegation grant/revoke/inspection and transactional audit. |
| Portals | `frontend/app/`, `frontend/components/`, `frontend/lib/{browser-api,server-api}.ts` | Protected layouts, sign-in, renewal and sign-out, invitations and recovery. Managers see eligible Team Member controls. Client admins manage project grants. Members see their current project authority. |
| Verification and setup | `backend/tests/`, `frontend/e2e/foundation.spec.ts`, `frontend/playwright.config.ts`, `scripts/test_backend.sh`, `scripts/seed_local.py`, `backend/app/seed.py`, `.github/workflows/ci.yml`, `README.md` | Real PostgreSQL and HTTP acceptance tests, Chrome verification, repeatable seeded workspaces and local setup. The test runner has its own Compose profile so service selection stays unambiguous while tests run. |
| Contracts | Database §5, API §§4.6–4.7, testing §16.2, `docs/DECISIONS.md` | Recorded the CP1-B project delegation scope, concrete endpoints and foundation decisions ADR-012–016. |

### CP1-B verification evidence

| Command | Result |
|---|---|
| `docker compose up -d --build --wait`, `python3 scripts/smoke.py` | Production images built. All five long-running services became healthy. The migration service exited 0. HTTP smoke checks passed against the running stack. |
| `sh scripts/test_backend.sh` | Ruff and strict mypy passed. All 16 Pytest cases passed against real PostgreSQL. Tested HTTP authorization, client isolation, mixed/elevated targets, independent client access after staff deactivation, audit and rollback, CSRF, session rotation, reset delivery, duplicate invitations, last-Admin protection and project-grant concurrency. |
| Local isolated PostgreSQL 16 run with `pytest -q`, `alembic upgrade head` and `alembic check` | All 16 cases passed on a second PostgreSQL instance. Migration head matched the ORM. |
| `npm run lint`, `npm run typecheck`, `npm test` in frontend | ESLint and TypeScript passed. Both Vitest cases passed. |
| `PLAYWRIGHT_CHANNEL=chrome npm run test:e2e` in frontend | All 4 Chrome tests passed against Compose. Covered both protected redirects, manager login/renew/logout, client portal isolation and two-session delegation grant/revoke. |
| `python3 scripts/seed_local.py` and database counts | Repeated seed preserved 7 synthetic users, 2 client organizations, 4 project roots, 3 agency memberships and 4 client memberships. Credentials are owner-readable under `.local/`. |
| `python3 scripts/check_specs.py` | Specification references, examples and all 108 documented permission cells passed. |

**Final checks.** Both the live database and the clean test database matched Alembic head `0003_recovery` and reported no outstanding ORM changes. An intermediate schema check reached a one-off test container while it was initializing. Assigning the test runner its own Compose service fixed the ambiguity. The final concurrent live and test checks passed. The runner removed its temporary database. A local scan found none of the generated database, n8n or demo credentials in 101 source and configuration files.

**Verification limits.** The local test HTTP client emits one Starlette deprecation warning. GitHub Actions is configured but has no remote run in this workspace. Chrome was the browser exercised. n8n service readiness and editor reachability were verified. External delivery, actual workflow orchestration and revision-specific binding decisions belong to later checkpoints. The password-reset mailbox and manual invitation links support local development.

## CP0 checkpoint report · 20 November 2026

**CP0 VERIFIED — specification reconciliation.** The owner approved delegated Team Member administration and project-scoped client sign-off. All four Milestone 0 exit criteria have been reviewed against the reconciled documents. No open CP0 blocker. The owner subsequently authorized CP1.

### Scope and repository baseline

Read AGENTS.md, CODEX_EXECUTION_PROMPT.md and all nine numbered specifications. The workspace contained the instructions, specifications, two frontend reference images and local tooling configuration. No application source, migration, Compose manifest, dependency manifest, test suite or Git working tree was present at entry. The database spec ended mid-table. Its reconstructed sections and the approved permission decisions are identified in the [decision log](DECISIONS.md).

### Milestone 0 exit review

| Roadmap §8 criterion | Evidence at the specification level | Result |
|---|---|---|
| Resolve blocking architecture conflicts | DB/API/AI/automation boundaries agree. ADR-010 and ADR-011 resolve P1 and P2 across the PRD, schema, API, frontend and acceptance tests. | Passed |
| Database supports required workflows | Database §§4.1–5 define guarded memberships, project-specific delegations, invitations, frozen inputs, proposal selections, generated tasks, immutable revisions, staged approval, jobs, event receipts, deduplication, reports and an ordered migration plan. | Passed at design level |
| API supports required transitions | API §§5–6 cover intake and conversion, brief review, proposal decisions, async polling, review submission, client feedback, report publication and scoped service callbacks. | Passed at design level. The action matrix identifies each privileged actor. |
| Explain end-to-end data flow | The four flows below identify the authoritative writes and the durable handoffs. | Reviewed |

### Integrated flows and dependencies

1. **Acquisition.** Native inquiry or verified Forms intake creates a lead and an outbox event together. The dispatcher sends the event to n8n for staff notification. Staff qualify and convert the lead in FastAPI, optionally creating the project in the same transaction. A separate invitation establishes client membership.
2. **Creative production.** An authorized client submits a project brief. Staff approval freezes a snapshot and emits brief.approved. n8n requests analysis and strategy jobs. A backend worker validates and stores outputs. A human selects a direction before planning. Selected plan items become tasks and draft deliverables. Internal approval releases a specific revision for submission. Only the owning client_admin or an active delegate for that project may bind the pending submitted revision. Other eligible members may comment.
3. **Operations.** Project membership governs assignments. Persisted assignments trigger notifications. Scheduled checks query FastAPI for eligible tasks and reserve each reminder by recipient, channel and local date. Client progress comes from authorized project aggregates and released milestones.
4. **Reporting.** Scheduled or manual generation snapshots verified project metrics for a unique period. The worker creates a draft narrative. Staff review and publish the report before the owning client can see it or receive a publication notification.

### Files changed

| Files | Change |
|---|---|
| AGENTS.md, docs/01_PRODUCT_REQUIREMENTS.md, docs/02_SYSTEM_ARCHITECTURE.md | Corrected the reading list, onboarding sequence, AI catalog and security references. Updated the PRD with both approved permission policies. |
| docs/03_DATABASE_DESIGN.md | Completed the truncated model and added cross-record constraints, execution contracts, guarded agency membership lifecycle, project approval delegations, atomic audit and migration order. |
| docs/04_API_SPECIFICATION.md | Aligned portal lists, invitations, state transitions, proposal actions, service calls and polling contracts. Added the RBAC matrix and role/delegation APIs. |
| docs/05_AI_SYSTEM_DESIGN.md, docs/06_WORKFLOW_AUTOMATION.md | Bound jobs to approved inputs and explicit actors. Defined workflow events, human gates, step idempotency and outcome handling. |
| docs/07_FRONTEND_UX_DESIGN.md, docs/08_IMPLEMENTATION_ROADMAP.md, docs/09_TESTING_AND_DEPLOYMENT.md | Aligned portal decisions, roadmap reading list and the date-only deadline example. Added frontend permissions and backend/browser acceptance cases in testing §16.2. |
| docs/DECISIONS.md, docs/IMPLEMENTATION_STATUS.md | Added the decision register with both owner-approved policies, checkpoint report, evidence and phase plan. |
| scripts/check_specs.py | Added a dependency-free static check for the documentation contracts, including positive and negative permissions in both matrices. |

### Verification

| Check executed | Actual result |
|---|---|
| `python3 scripts/check_specs.py` | Passed. Both instruction files reference the nine specs on disk. Checked local link targets, table widths and fence balance across 13 Markdown documents. Parsed 21 JSON examples. Matched workflow HTTP calls against the API catalog, checked late database entities, compared AI polling states, and checked event registry coverage. |
| Two negative controls in a temporary copy | Passed. The checker rejected the original truncated database row and an intentionally unlisted internal workflow route. |
| RBAC matrix tests in `python3 scripts/check_specs.py` | Passed all 108 cells, covering 9 operations × 6 actor contexts in each of the API and frontend matrices. |
| Three RBAC negative controls in temporary copies | Passed. Detected manager elevation, an undelegated member gaining sign-off and a delegate losing the revision-request action. |
| Manual contract trace | Traced the four business flows against the data model, API, human decisions, worker or n8n handoff, portal visibility and failure paths. Traced each approved delegation policy through storage, API actions, frontend controls, audit and tests. |
| Git status at entry | Unavailable. This directory and its parents contain no Git working tree. Changes were compared to a temporary pre-edit copy. |

Application linting, TypeScript checks, migrations, Pytest, Vitest, n8n integration tests, Playwright and Compose smoke tests were **not run**. Their inputs do not yet exist. Live and development adapters have no execution results.

### Checkpoint plan and review gates

| Checkpoint | Dependency and deliverable | Verification required before review |
|---|---|---|
| CP1 · M1–2 | Reviewed CP0 and explicit start authorization → Compose, database, sessions, RBAC and portal boundaries | Service readiness, migrations, login/renewal/logout, CSRF, delegated team administration, last-Admin races and cross-client tests |
| CP2 · M3–4 | Identity and client scope → inquiry, invitations, conversion, projects, assignments, outbox and first notification | Concurrent conversion/redemption, grant/revoke constraints, isolation, notification retry and browser onboarding |
| CP3 · M5–6 | Projects and workers → files, brief snapshots, validated generations, proposal selection and Creative Studio | Authorized uploads, validation failure, worker restart, idempotency and human direction selection |
| CP4 · M7–8 | Versioned creative work → review cycles, client feedback and scheduled reminders | Delegated sign-off, revoked authority, stale and concurrent decisions, release visibility, timezone boundaries and duplicate schedules |
| CP5 · M9–10 | Operational and creative history → period metrics, reviewed reports, execution monitoring and evaluation | Period uniqueness, verified metrics, published-only access, recoverable failures and measured evaluation |
| CP6 · M11 | Integrated CP1–5 → reproducible demonstration and final documentation | Full E2E, security, accessibility, migration and Compose verification |

Each checkpoint ends at review. Mechanistic Interpretability (M12) is outside the MVP. The owner subsequently authorized CP1 Foundation (M1–2). FastAPI enforcement, executable database migrations and API integration test execution belong to the implementation checkpoints above.
