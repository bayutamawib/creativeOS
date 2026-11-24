# CREATIVE OS — Implementation status

## CP8-B Secure Video Media Management — owner review

**Implemented and verified locally on 22 November 2026.** CP8-A's report, authorization paths, media tests, and mobile gallery capture were reviewed before extension. The CP8-A report records its own original acceptance evidence; this checkpoint reran the image media tests as part of the current suite. Existing working changes and the owner's `cek_groq.py` remain uncommitted and untouched.

MP4 uploads use the existing authenticated file route and private local volume. `VIDEO_MAX_BYTES` defaults to 50 MiB and is configurable from 1–500 MiB. The server checks filename/media type and complete top-level MP4 boxes while writing bounded request chunks to a private temporary file, then hashes and atomically stores it. A manual PNG/JPEG cover is optional; a same-project foreign key and service validation enforce matching project and visibility. The cover is locked when the video enters a revision. Project cards select the newest authorized image or video and show a play indicator; video without a cover uses gradient artwork. Creative Asset and exact revision galleries show video with native controls, a Fullscreen action, and authenticated seeking. The existing agency release and client decision bind to the same revision.

The video stream and download routes reauthorize each request and verify the stored hash with 1 MiB reads before returning 64 KiB chunks. Full GET/HEAD, valid single Range, and invalid or unsatisfiable Range return 200, 206, and 416 respectively. Video bytes are never served from a public static path or held as a complete backend byte array. An internal cover becomes available to the owning client only with its released video revision. Migration `0015_video_cover` adds the nullable same-project cover reference.

### Executed verification

| Check | Result |
|---|---|
| Isolated backend `ruff check app alembic tests/test_media.py`, strict `mypy`, `alembic upgrade head`, `alembic check` | Passed; no schema drift |
| PostgreSQL `pytest -q --tb=short tests/test_media.py` | 4 passed; includes CP8-A image cases and CP8-B validation, configurable limit, cover scope, 200/206/416, release and revocation. One upstream TestClient warning |
| PostgreSQL `pytest -q --tb=short tests/test_projects.py tests/test_reviews.py` | 15 passed; one upstream TestClient warning |
| Frontend `npm run typecheck`, `npm run lint`, `npm test` | Passed; seven Vitest tests |
| Isolated production backend/frontend Docker build and health | Passed |
| Chrome Playwright `video.spec.ts` on isolated fixture stack | 1 passed in 2.4 minutes on the final run. Chrome recorded a small synthetic H.264 MP4. Covered optional cover, project fallback/play indicator, both portal players, fullscreen, seek, 206 through Next.js, 404 before release, released revision video, and client approval |

The first browser review attempt used a client-visible project video as an internal revision attachment; FastAPI correctly returned 422 under the existing private-attachment contract. The test now uploads a separate internal video and verifies its pre-release denial. Earlier test harness attempts were corrected before the final pass. No live LLM call was made.

### Limits and review

Video is local-storage only. The container parser verifies the top-level structure and signature, not codec compatibility or semantic correctness of every nested atom. Browser playback depends on its codec support. Every Range request rehashes the whole file before streaming, so seeking large files trades CPU and disk reads for integrity without a shared cache. One byte range per request is supported; multiple ranges return 416. A process crash during upload can leave a private `.incoming-*` temporary file for operator cleanup. No transcoding or timestamp comments are included. No commit, push, or external deployment was performed.

### Main local OAT environment · 22 November 2026

The existing PostgreSQL volume was preserved and advanced from `0014_schedule_heartbeat` to non-destructive `0015_video_cover` through the Compose migration service. Backend and frontend were rebuilt; the worker was recreated from the updated backend image after its old schema check became unhealthy. All five services now report healthy. The local configuration uses fixture AI (`fixture-v1`) and private local files; its model label had retained the Groq name and was corrected without changing credentials. The repository smoke probe passed API readiness, the protected session boundary, web, and n8n. Main-stack Chrome checks passed `video.spec.ts` (one test, 36.3 seconds) and `media.spec.ts` (one test, 32.9 seconds). The first image-test attempt stopped before any writes because the fixture-mode guard detected the stale model label; it passed after correction. The video test created a synthetic project, [Video review e2ee17](http://localhost:3100/admin/projects/a14f64ac-00b9-4d2b-b22c-cf909a79f22c), and the image test created its own synthetic project. Existing projects were not edited.

Owner OAT entry points: agency and client users sign in at `http://localhost:3100/login`, then use `/admin/dashboard` or `/client/dashboard` according to role. `manager@example.com` and `lead@example.com` are the seeded agency and client examples. Passwords remain only in the owner-local, Git-ignored `.local/demo-accounts.json`. Use the synthetic projects or create a new clearly named test project. Check image card and preview; MP4 upload with and without a cover; project play artwork; video play, seek, and fullscreen; 404 for an internal video before release; exact revision release; client video preview and approval; and continuing visibility of an older released revision after a new draft. CP8-B awaits manual owner acceptance. No CP9 work has begun.

## CP8-A Creative Media Gallery and Visual UX

**Verified locally on 22 November 2026.** CP7 was audited with the existing secret scanner and committed as `f60cee5` before implementation. The owner’s untracked `cek_groq.py` troubleshooting file was retained outside that baseline. Existing Git history and PostgreSQL, n8n and private file volumes were preserved.

Project lists now use responsive image cards with client labels for agency readers, status, milestone progress and deadline. Existing search, pagination and management entry points are retained. The newest image authorized for the selected portal provides the cover, with gradient artwork when none is accessible. Cover choice is automatic. Project details share a media gallery, image upload control, downloads and an accessible native preview dialog. Revision galleries and approvals render images belonging to the exact authorized revision. The existing release confirmation and binding client decisions are preserved.

### Files and contracts

- Backend changes in `api/{briefs,projects,reviews}.py` and `services/{projects,reviews}.py` add authorized thumbnail/preview delivery, bounded cover lookup, optional project filtering for approvals and attachment MIME metadata. PNG thumbnails fit within 640 × 480. Preview and thumbnail reads verify stored hashes and reuse project, file and released-revision scope with private no-store responses. No migration was required.
- Shared frontend components `media-card.tsx`, `project-media.tsx` and `project-media-upload.tsx` integrate with both project detail pages, the project list and the review queue. Existing file upload and download contracts remain available. Direct same-origin image URLs bypass shared image optimization. The file identity, media type and modal are separated from project and review presentation so CP8-B can extend supported media rendering.
- Updated PRD, API, frontend and testing specifications and ADR-036. Added PostgreSQL media tests, a synthetic PNG fixture and a Playwright gallery test.

### Executed verification

| Command or check | Actual result |
|---|---|
| `ruff check app tests`, strict `mypy` in the isolated backend test service | Passed |
| `pytest -q --tb=line tests/test_media.py tests/test_briefs.py tests/test_projects.py tests/test_reviews.py` | 22 passed in 70.74 seconds. The initial cover lookup emitted a SQLAlchemy deprecation warning |
| `pytest -q --tb=line tests/test_media.py tests/test_projects.py` after replacing that deprecated lookup with the supported PostgreSQL distinct_on extension | 9 passed in 48.27 seconds. One upstream TestClient warning |
| `npm run lint`, `npm run typecheck`, `npm test` | Passed. Seven Vitest tests passed |
| Isolated production frontend and backend Docker builds | Passed. The isolated API and web frontend reported healthy |
| `PLAYWRIGHT_BASE_URL=http://localhost:3310 PLAYWRIGHT_CHANNEL=chrome npm run test:e2e -- media.spec.ts projects.spec.ts` | Two passed in 1.5 minutes. Covered image upload, agency/client cards, preview focus and Escape, release cancellation, released images, replacement draft isolation, project management and notifications |
| Targeted media capture pass with image decode waits | One passed in 25.9 seconds. Five screenshots captured and visually reviewed |

Final `scripts/smoke.py`, `alembic check`, specification checks, `git diff --check` and the existing secret scanner passed. All five isolated Compose services were healthy. The scanner covered 359 Git blobs and 264 working paths. PNG validation and OCR credential checks passed for all five screenshots and the synthetic image fixture.

The first backend test attempt overlapped a database-container recreation and failed during connection setup. It was rerun against the healthy database. The first gallery browser attempt read the new draft before its create response arrived. Explicit response waits fixed the test harness. Final browser checks used the deployed gallery implementation.

Authorization tests cover anonymous readers, unassigned staff, other clients, other projects, archived files, revoked membership and non-image previews. An internal revision image stays inaccessible until release. A later draft leaves the released revision visible without exposing replacement content. Both image endpoints set private no-store, Vary Cookie, nosniff and inline disposition. No live AI request was made.

### Reviewed screenshots

| View | Capture |
|---|---|
| Agency project gallery and filters | [Agency project cards](screenshots/cp8/agency-project-gallery.png) |
| Client project gallery | [Client project cards](screenshots/cp8/client-project-gallery.png) |
| Enlarged project image | [Client image preview](screenshots/cp8/client-image-preview.png) |
| Exact released revision | [Released revision preview](screenshots/cp8/released-revision-preview.png) |
| Responsive project assets | [375px client gallery](screenshots/cp8/client-mobile-gallery.png) |

### Limits and next checkpoint

Covers derive from the newest accessible image and have no manual pinning. Thumbnails are generated on demand and use no shared cache. The gallery pages existing project files in groups of 50, and the released revision history uses the existing review listing. File support remains validated PNG, JPEG and the existing text downloads. Video playback and processing remain deferred to CP8-B. CP8-A stops for explicit owner review.

## CP7 Controlled Groq verification

**Controlled live copywriting generation verified on 21 November 2026.** The resumed CP7 run used Groq through the existing compatible adapter with `User-Agent: CreativeOS/1.0`, `openai/gpt-oss-20b`, 4096 output tokens and a 30-second timeout. The raw report-output debug print introduced during manual troubleshooting was removed. Schema and validator behavior were preserved.

The synthetic draft and approved brief were prepared in fixture mode. On the isolated stack the worker and n8n were stopped and zero pending/running jobs were confirmed. The existing authenticated API submitted the sole eligible copywriting job `fe950383-d38e-47f2-ad9a-8ce86038d9f1`. A one-shot invocation of the existing runner counted **one outbound completion request**. PostgreSQL persisted `completed`, attempt **1**, provider `compatible`, model `openai/gpt-oss-20b`, 1,002 input tokens, 917 output tokens and 1,660 ms latency. Pydantic accepted headline, caption, call_to_action, hashtags, revision_notes and potential_risks. No retry occurred. A targeted Chrome check confirmed the persisted headline and save-as-revision control in Creative Studio. The owning client received 403 for the private draft and saw no deliverable or generated headline. Provider billing was unavailable. The manual diagnostic summary calls described by the owner are separate from this single controlled copywriting attempt.

Targeted provider tests passed **4 tests**, with 5 deselected and one upstream TestClient warning. Tests cover the User-Agent header, JSON mode, token response parsing, missing credentials and bounded failures. Ruff passed. Successful generation establishes transport and schema behavior for this synthetic case. Editorial quality and real-client accuracy require human assessment.

The isolated backend and worker were restored to `fixture / fixture-v1` without a live key. All five services returned healthy after n8n bootstrap. The successful generation remained at attempt 1. The README, operations guide and ADR-035 record the live boundary and verification. No full regression suite was repeated.

### Earlier controlled attempt

A synthetic fixture-created private draft was used on the isolated Compose stack. The queue had zero pending or running jobs before submission. The continuous worker and n8n were stopped. The existing authenticated copywriting API queued job `625b32a2-32e7-4a32-a1bf-cdb87bc76e3b` as the only eligible generation.

The one-shot runner counted **one outbound completion attempt** to the approved Groq HTTPS endpoint with `openai/gpt-oss-20b`, a 512-token cap and a 15-second timeout. PostgreSQL recorded provider `compatible`, attempt **1**, status `failed`, error `provider_http_error` and 158 ms latency. The runner saved no output or token counts. Groq documents JSON object mode for the model and still lists `max_tokens` as deprecated. The adapter's safe error category omits the upstream HTTP status, so the specific rejection cause and any charge are unknown. No second attempt was made. [Groq model card](https://console.groq.com/docs/model/openai/gpt-oss-20b) · [Groq API reference](https://console.groq.com/docs/api-reference)

The targeted Chrome check showed the persisted error in Creative Studio. The owning client received HTTP 403 for the private draft and saw no deliverable in the approvals UI. Output-schema validation and successful suggestion rendering were not reached in this live attempt. The isolated backend and worker returned to `fixture / fixture-v1` with no live key. The Compose smoke check passed and the failed job still showed attempt 1 after restoration. The CP6 fixture verification remains the baseline.

## CP6 Final Integration and Portfolio Demo

**CP6 complete for the local portfolio MVP.** CP6-A passed the integration gates and CP6-B completed the demo and documentation handoff. The local CP5 baseline is `f6772dc`. The n8n pre-persistence redaction limitation is recorded below.

### CP6-A integration pass on 21 November 2026

- On the isolated Compose project, `docker compose up --build -d --wait --wait-timeout 900 frontend` built the current production frontend. `PLAYWRIGHT_BASE_URL=http://localhost:3310 PLAYWRIGHT_CHANNEL=chrome npm run test:e2e -- intake.spec.ts` passed in 1.8 minutes. Inquiry, invitation, approved brief, AI fixture, revision request and sign-off, task assignment and completion, and report publication all used project `daa89fae-7170-422d-bd47-f67e92a815e1`. Published report `b5f88831-a1d8-4f4b-8b4e-0902f4887835` showed two tasks, one completion, one client approval and one revision request. The client saw the report only after publication. Publication execution **713** matched event `be02a64f-c8e0-4a3a-8871-dbc38efad26d` and its delivery.
- The earlier Compose startup terminated while n8n was unhealthy, leaving the worker unstarted. `docker compose up -d --no-build --wait --wait-timeout 90 worker` completed after n8n published all nine workflows. The primary frontend now uses the verified image. All five long-running services and the workflow registration probe reported healthy. `python3 scripts/smoke.py`, `docker compose exec -T backend alembic current` and `docker compose exec -T backend alembic check` passed on both stacks. The migration service exited 0. Both databases are at `0014_schedule_heartbeat` with no drift. The primary database kept its 23 users and seven reports. The PostgreSQL, n8n and file volumes were retained.
- **n8n retention limit.** In the installed n8n 2.48.6 regular execution path, the standard JWT Webhook node authenticates and includes its full request headers in trigger output. `ActiveExecutions.add` persists the initial data before a downstream node can alter it, and the built-in redaction applies to viewed/streamed execution data. The save switches suppress retained completed, failed, manual and progress data, but do not prevent that initial SQLite write. Execution **716** had one bearer-bearing payload row immediately after completion and zero payload rows after the configured one-minute pruning sweep. The independent verifier still correlated it with event `a0169c7d-b89d-4be2-b858-261b1a2e964a` and two inbox deliveries using the terminal journal. An authorized application monitoring request showed the execution ID and completion status without raw headers or envelopes. An unauthenticated webhook returned 401.
- The 30-second JWT, loopback binding, restricted metadata and backup access, disabled payload history and frequent pruning limit the remaining exposure. A privileged SQLite reader or a backup can still see the token before pruning. Pruning verifies removal from ordinary database queries. Historical backups and SQLite file blocks are outside that guarantee. Strict pre-persistence stripping would require a supported trigger option or a separately reviewed ingress that authenticates and strips headers before handing the event to n8n. No custom runtime patch was applied.
- `python3 scripts/check_specs.py`, `python3 scripts/check_secrets.py`, `git diff --check` and `docker compose config --quiet` passed. The Git scan covered 305 distinct blobs and 240 working paths. A sample of 300 log lines per isolated service contained no configured secrets or raw bearer JWTs. The primary environment and synthetic account files are mode 0600.
- `npm run lint`, `npm run typecheck` and `npm test` passed. Vitest passed seven tests, including bounded GET retry and single-attempt POST. Production Next.js compilation and type checking passed as part of the isolated Compose build.

- `sh scripts/test_backend.sh` passed **66 tests in 307.45 seconds** with one upstream TestClient deprecation warning. Ruff and strict mypy passed. The runner applied every migration to a separate temporary PostgreSQL database and found no schema drift. The suite covered role and tenant boundaries, conflicting and stale approvals, session and CSRF behavior, upload controls, rate limits, outbox retries, uncertain delivery and AI fixture validation.
- The first complete Chrome run passed 10 of 11 cases. Its final test polled a queued generation for 15 seconds before the restarting worker was ready. PostgreSQL recorded completion on the first attempt after approximately 24 seconds in the queue for job `5962fc81-5d5a-4532-813e-c9379f07da42`. The browser harness now waits for the Compose worker health check before polling generation and testing release delivery.
- The full Chrome rerun, `CP3_TEST_WORKER_RESTART=1 CP4_TEST_WORKER_RESTART=1 PLAYWRIGHT_BASE_URL=http://localhost:3310 PLAYWRIGHT_CHANNEL=chrome npm run test:e2e`, passed **11 tests in 6.5 minutes**. Generation and release deliveries recovered after worker restarts. The repeated portfolio journey published report `cf271e82-a8ee-4c34-9f45-478d45c1a223`. Publication execution **764** matched event `18eb89bd-e7c8-482d-8213-b641b28d7224`. The mobile test checked labels, keyboard navigation, visible focus, feedback, reduced motion and 375px portal layouts. The desktop review cycle covered dialog focus, cancellation and release. The login button contrast was 6.29:1. Single local samples put DOM readiness at 1,115 ms for the agency dashboard and 632 ms for the client dashboard. The fixture evaluation run `9fab4925-3386-4280-adde-153bf91ce9d3` passed schema, grounding and required-field checks on 50 outputs and rejected all six negative controls as expected. These results cover the local fixture and synthetic dataset.
- A final targeted Chrome run of `studio.spec.ts` with both restart flags passed in 46.6 seconds. The helper waits for worker health with `docker compose up -d --no-deps --no-recreate --no-build --wait --wait-timeout 60 worker`. PostgreSQL and n8n container IDs stayed unchanged through both restarts. Fixture generation `47983e5d-faec-4ddf-884f-0aac49d92b31` completed and release event `017df992-7a26-46eb-8fff-fa07547778ee` matched n8n execution **783**. Targeted ESLint and TypeScript passed with this final helper.
- Deadline reminder n8n execution **738** matched event `fc6d7f03-6393-53de-9563-be15a048fd8e` and originating schedule **736**. With the isolated minute schedule, `python3 scripts/verify_workflow.py report.schedule 3cb79559-b4bc-415b-ba0a-962b4de64713` verified n8n execution **744**, PostgreSQL run `143498be-6832-4e04-a4e0-cd9bb17e0abf` and completed summary job `3c691702-7fe0-4b20-8ce8-d59d54dbddd6`.

### Targeted checks on 21 November 2026

- In `frontend/`, `npx --no-install vitest run tests/read-api.test.ts`, `npx --no-install eslint lib/read-api.ts lib/server-api.ts tests/read-api.test.ts` and `npm run typecheck` passed.
- Ran `pytest -q -s tests/test_briefs.py` in the isolated Compose test service with the current backend sources. Five tests passed in 9.72 seconds with one upstream TestClient deprecation warning. Targeted Ruff lint and format checks passed.
- In the isolated Compose project, `python3 scripts/verify_workflow.py lead.created 581043fd-9c83-499f-9202-4410720bb826` matched event `14622759-ea2e-4b21-8f99-7141a9482fc2` to n8n execution **673** and two development inbox deliveries. Read-only SQLite counts showed **1** payload row with a bearer header immediately after completion and **0** payload and bearer rows after pruning. The same verifier passed from the n8n terminal journal after pruning. This demonstrates limited retention alongside PostgreSQL correlation. It leaves temporary access for someone with privileged access to n8n storage.
- `docker compose config --quiet` and `git diff --check` passed.

### CP6-B portfolio handoff on 21 November 2026

- Finalized the [portfolio README](../README.md), [one-project demo walkthrough and screenshot gallery](PORTFOLIO_DEMO.md), and [operations guide](LOCAL_OPERATIONS.md). The guide records integration readiness, the remaining n8n JWT exposure and production hardening, and the optional one-request live provider procedure. The live LLM transport, Google Drive and live Google Forms delivery remain unverified. The application implements the Forms receiver. Upstream Forms forwarding, Gmail and Telegram delivery remain unimplemented.
- Captured **11 screenshots** on the isolated Compose stack in Chrome. They cover both dashboards, Creative Studio, client approval and the agency release modal, project and task management, a published report, monitoring, fixture evaluation and two published n8n canvases. The gallery uses several synthetic projects. One supplemental capture attempt timed out at login and another at a review transition. Completed states were captured directly from the persisted CP6-A synthetic records. The accepted single-project journey and full regression evidence are recorded above.
- Ran the documented `docker compose run --rm -T --no-deps -e AI_PROVIDER=fixture -e AI_MODEL=fixture-v1 backend python - < scripts/check_summary.py` on the isolated stack. It validated the synthetic report summary. Only fixture mode was exercised.
- Verified the Markdown links and anchors, four localhost links, and every screenshot reference. Inspected the captures visually and checked PNG signatures, dimensions, OCR text, known local credential matches and address domains. The captures contain synthetic `example.com` identities and omit private invitation links, credentials and headers. `python3 scripts/check_specs.py`, `python3 scripts/check_secrets.py`, `python3 scripts/smoke.py` and `git diff --check` passed.
- CP6-B changed documentation and screenshot assets. CP6-A supplied the passing regression results. The local n8n editor showed intermittent readiness errors during capture and both workflow canvases loaded on retry. The Git baseline and persistent volumes were retained.

## CP5 Reporting, Monitoring and AI Evaluation

**CP5 VERIFIED on the local Compose stack.** The CP5-A gate passed before monitoring and evaluation implementation began. The owner reviewed CP5 and authorized CP6.

### CP5-A · VERIFIED

Local baseline `178100f` preserves the 48-file CP4 change set. Reviewed the diff and staged paths, checked staged bytes for generated credentials and secret patterns, and confirmed local environment files, private uploads and database artifacts are excluded. Both development volumes were retained.

Added project reports, frozen metric provenance, version-checked narrative review and publication, JSON downloads, agency analytics, scheduled generation and recipient-specific draft/publication notifications. Migration `0011_reports` links report summaries to the existing durable generation queue. The two portals share the report display with separate server-authorized actions.

| Area | Files changed |
|---|---|
| Backend | Alembic metadata and `versions/0011_reports.py`, `app/{report_models,ai_models,main}.py`, `ai/{reporting,runner}.py`, `api/{reports,inbox,workflows}.py`, `services/{reports,report_schedule,workflows}.py` |
| Automation | `workflows/{report-schedule,report-notifications}.json`, n8n bootstrap, Compose, environment example, workflow verifier |
| Frontend | Both portal layouts, inboxes, report lists and detail routes, `components/{reports,report-actions}.tsx` |
| Tests and documentation | `tests/{test_reports,test_reviews}.py`, `e2e/reports.spec.ts`, README, API specification, ADR-028/029 and this file |

`sh scripts/test_backend.sh` passed **57 tests** on migrated PostgreSQL, including the CP1–CP4 suites, Ruff, strict mypy and a clean Alembic drift check. Checks cover the 23-hour New York DST day, period boundaries, two simultaneous reservations, exact client revision outcomes, conflicting publication requests, model-claim rejection, recovery using original metrics, draft/export isolation and cross-project reads. One upstream TestClient deprecation warning. Frontend lint, TypeScript, two Vitest tests, production build and the report Playwright journey passed. The browser generated, reviewed, published and downloaded the same report. `scripts/smoke.py`, `scripts/check_specs.py`, Compose configuration and diff checks passed.

Independent n8n execution metadata and PostgreSQL matched. Draft execution **102**, event `ac61f462-7a5f-4eb6-bc76-14c3e98661c2`, and publication **103**, event `6efb60e3-e3ff-4f45-bb7d-7f908b472b00`, each delivered two development inbox messages. Weekly schedule execution **105** matched PostgreSQL run `432ee5f9-53c7-4aa4-a943-407e7ade5960`, report `233f7601-0bdf-43d4-b07f-63cff0ef52f1` and completed summary job `9bf03ac0-b255-4d3d-8473-469555fa5904`. Used a temporary per-minute schedule for the exercise. The normal configuration schedules Monday at 09:00 agency time.

The verified provider was `fixture / fixture-v1`. Narratives require human publication. Current-state metrics carry their collection timestamp. The report does not reconstruct past backlogs.

### CP5-B · VERIFIED

Added manager-only activity lists with state filters, correlated event details, workflow attempts, safe failure categories, consumer receipts, recipient delivery attempts, generation timing and authorized retries. The worker classifies expired sending claims as uncertain. Attempt counters and prior workflow runs survive manual retries. Local notifications and delivery history commit together. Migrations `0012_monitoring_evaluation`, `0013_dispatch_error` and `0014_schedule_heartbeat` preserve earlier records and backfill confirmed local delivery attempts from existing notifications.

The evaluation runner executes ten versioned synthetic briefs through analysis, strategy, planning, copywriting and report summarization. Each case records the synthetic source, validated output, observed checks and elapsed time. Negative controls exercise malformed JSON, missing fields, an unsupported claim, an obsolete brief snapshot, a client initiating an agency generation and a plan without an approved direction. Database-dependent controls use real FastAPI services inside a rolled-back PostgreSQL savepoint. The dashboard and local CLI use the same authenticated API. Human reviewers can score individual outputs and record grounding, safety and acceptance separately.

| Area | CP5-B files changed |
|---|---|
| Database and worker | `backend/alembic/env.py`, `versions/{0012_monitoring_evaluation,0013_dispatch_error,0014_schedule_heartbeat}.py`, `app/{operations_models,ai_models,quality_models,main}.py`, `ai/runner.py`, `services/{monitoring,workflows}.py` |
| Evaluation | `backend/app/ai/evaluation.py`, `ai/datasets/creative-v1.json`, `app/api/{evaluation,monitoring}.py`, `scripts/evaluate.py` |
| Portals and evidence | Agency layout, `app/admin/automation` and `app/admin/evaluations` list and detail pages, `components/evaluation-actions.tsx`, `e2e/monitoring.spec.ts`, `backend/tests/test_evaluation_monitoring.py`, README, API specification and ADR-030/031. Also updated the weekly schedule workflow, `services/report_schedule.py` and `tests/test_reports.py` for callback expiry and replay across period boundaries |

A CLI invocation produced run `bcc2b76f-bab9-4e61-9f9f-e74f92097ac9`. A separate dashboard run `51450d20-d9f6-4b33-9d0d-1dc8234f7052` produced the same 50 schema-valid, required-complete and grounded outputs and six expected control rejections. The dataset SHA-256 is `01e584f01ffbbd23757b28a05807869bd43c43b0b214b9b4419502342851db3e`. PostgreSQL case counts matched the aggregates and the hash of the dataset file. Total measured fixture execution time was 25 ms and 6 ms respectively. Both runs used `fixture-v1` and prompt `creative-v1`. Tokens were unavailable. No human reviews or model-quality scores were recorded in the development database. Isolated tests exercise human scoring and reject acceptance after a critical finding.

On the monitored stack, n8n publication execution **128** matched PostgreSQL workflow run `7b6742de-38bf-40c4-9823-1aa53951e0ee`, event `f56fdff6-1f7c-484a-8f2b-4ddd5497a365`, report `dc2b580a-514f-4fec-9b17-5af8ff249d1a`, receipt `db14f14f-13e3-4c22-8fbb-26326c289ed7` and two completed attempts for two distinct recipients.

The final isolated PostgreSQL run, `sh scripts/test_backend.sh`, passed **63 tests in 56.21 seconds**. Ruff and strict mypy (62 application modules) passed. Alembic upgraded a clean database through `0014_schedule_heartbeat` and found no model drift. The existing development database upgraded in place. Tests cover repeatable results, dataset version conflicts, critical human review findings, access denial to both client organizations and agency staff, protected monitoring projections, retry authorization, duplicate retries, terminal transport rejection, replay of the same transiently failed generation and uncertain-send suppression. Interrupting the synthetic schedule heartbeat in PostgreSQL failed the orchestration attempt, preserved the job and let a later schedule recover the original report. The suite emitted one upstream Starlette TestClient deprecation warning.

After the heartbeat change, successful n8n execution **154** matched PostgreSQL run `5256b80e-a6d3-4a23-8a3d-12bfb56d89a3`. It covered three distinct project reports, including `128f0dc3-cdda-4d72-b262-cef2f530889f` with completed summary generation `61699fe7-ea8e-4340-b319-94112729b372`. `python3 scripts/verify_workflow.py report.schedule <report-id>` checked n8n execution metadata separately from PostgreSQL.

Final `CP3_TEST_WORKER_RESTART=1 CP4_TEST_WORKER_RESTART=1 PLAYWRIGHT_CHANNEL=chrome npm run test:e2e` passed **10/10 Chrome journeys in 1.4 minutes**, including CP1–CP4 regression paths, both worker restarts, report publication/download, monitoring receipts and the evaluation dashboard. An earlier run caught an automation table regression because a timestamp shared the event name's cell. Separate columns restored the original accessible event name and the existing assertion passed. The independent monitoring journey also passed alone in 10.8 seconds after it was made to create and follow its own inquiry event. The final full browser run confirmed report draft execution **162** (event `12bf649f-c143-40d9-a80a-f7dab3d8b8ae`) and publication **163** (event `fadf7857-ebe2-4b8b-aa95-3276dc53917f`). Each delivered to two development recipients.

Other commands passed: frontend `npm run lint`, `npm run typecheck`, `npm test` (2 Vitest tests), production image builds, `docker compose config --quiet`, `docker compose up -d --build --wait`, `python3 scripts/smoke.py`, `python3 scripts/check_specs.py` (9 specifications, 21 JSON examples, 132 matrix expectations) and `git diff --check`. For the real timer test, Compose temporarily ran n8n with `REPORT_CRON='* * * * *'`. The restored container reports `0 9 * * 1` in `Asia/Jakarta`. All five services passed readiness. Final checks covered all 54 changed files for local secrets and sensitive paths. A scan of 709 requests in the current backend container log found zero 5xx responses, only the expected structured request fields, and no matching generated credentials.

**Limits and next gate.** The measured results cover fixture execution, schema and selected evidence checks. Semantic quality awaits human review. Uncertain external sends were exercised with interrupted synthetic records in isolated PostgreSQL. Local n8n and development inbox delivery were verified. Live LLM, Gmail, Telegram and Google Drive integration remain unverified. No paid requests or public deployment occurred. CP5 changes remain in the working tree for checkpoint review. The CP4 baseline is the latest local commit.

## CP4 Content Approval and Operational Automation

**CP4 VERIFIED on the local stack.** CP4-A passed before CP4-B began. All five Compose services passed readiness. The owner subsequently authorized CP5.

**Preflight passed.** Reviewed the CP3 inventory and checked the diff, staged paths and staged bytes for generated credentials, demo passwords, private keys and sensitive paths. Created local baseline `c28175d` from 57 changed files. No remote was configured. Existing PostgreSQL and n8n volumes were preserved.

### CP4-A · VERIFIED

Added revision-bound reviews and feedback, recorded signer membership and delegation, historical release projections, revision attachments and human editing. The CP3 copy-save path also supersedes pending reviews. The agency queue and client approvals page use backend-permitted actions. ADR-026 records the confirmed release policy, now reflected in the PRD, API and frontend matrices, database contract and acceptance specification.

Changed migrations `0009_reviews` and `0010_revision_files`, Alembic metadata, the content revision model, review models/services/API, Studio and file services, portal navigation and approvals pages, the review queue component, PostgreSQL and browser tests, and the specification checker.

`docker compose up -d --build --wait`, `sh scripts/test_backend.sh`, frontend ESLint, TypeScript, Vitest, Playwright, the smoke probe and specification checker passed. The fresh PostgreSQL run passed **48 tests** including release rollback, two concurrent releases, opposing client decisions, revocation racing sign-off, inactive membership, internal-file visibility and supersession. **Eight Chrome journeys** passed in 46.1 seconds. The review journey cancelled with both Cancel and Escape, verified the client still could not see the draft, confirmed revision 2, requested changes as the client and approved the separately released revision 3. Both Vitest tests passed. The specification checker verified 132 matrix entries. One upstream Starlette TestClient deprecation warning.

### CP4-B · VERIFIED

Three new n8n definitions implement review notifications, deadline scans and reminder delivery. The timer authenticates to FastAPI and records its n8n execution ID with durable reminder reservations. The dispatcher sends signed webhook requests. FastAPI checks the exact release, current membership, task state and assignments at delivery. Local delivery records and processing receipts share a transaction. Both portals expose the appropriate recipient inbox. Admins and Agency Managers can inspect recent workflow activity.

| Area | CP4 files created or modified |
|---|---|
| Schema and server | `backend/alembic/env.py`, `versions/{0009_reviews,0010_revision_files}.py`, `app/{ai_models,review_models,config,main}.py`, `app/api/{inbox,reviews,studio,workflows}.py`, `app/services/{assets,studio,reviews,review_notifications,reminders,workflows}.py` |
| n8n and runtime | `automation/n8n/{bootstrap.sh,ready.cjs}`, `workflows/{approval-notifications,deadline-notifications,deadline-schedule}.json`, `compose.yaml`, `.env.example`. CP4-B uses the existing PostgreSQL outbox, workflow runs, processed events and notifications tables. |
| Portals | Agency and client layouts, approvals and notifications pages, agency automation page and `frontend/components/review-queue.tsx` |
| Verification and contracts | `backend/tests/{test_reviews,test_reminders}.py`, `frontend/e2e/{review-cycle.ts,projects.spec.ts,studio.spec.ts}`, `scripts/{verify_workflow,check_specs}.py`, README, specifications 01, 03, 04, 06, 07 and 09, this status report and ADR-026/027 |

Final `sh scripts/test_backend.sh` built a fresh test schema inside a temporary Compose PostgreSQL database. Ruff passed, strict mypy passed for 53 application modules, migrations applied through `0010_revision_files` and Alembic detected no drift. **53 tests passed in 28.33 seconds**, with one upstream Starlette TestClient warning. The suite includes conflicting internal decisions, service-identity denial, parallel schedule callbacks, same-day delivery deduplication, Asia/Jakarta midnight and New York timezone checks, completed/unassigned task suppression, membership revocation, and recovery after a committed delivery loses its acknowledgment. CP1–CP3 tests ran in the same suite.

`docker compose config --quiet`, `docker compose up -d --build --wait` and `python3 scripts/smoke.py` passed. Existing volumes were preserved. Frontend `npm run lint`, `npm run typecheck` and `npm test` passed, including both Vitest tests. `python3 scripts/check_specs.py` and `git diff --check` passed. An earlier concurrent regression run timed out awaiting the delegation control and caught a browser test reloading the inbox before navigation completed. The review test now waits for the exact notification destination.

The final sequential run of `CP4_TEST_WORKER_RESTART=1 PLAYWRIGHT_CHANNEL=chrome npm run test:e2e` passed **all eight Chrome journeys in 1.4 minutes**. The browser confirmed revision 2 with the worker stopped, then followed the client inbox link after restart. The client requested changes, the agency edited and released revision 3, and the client approved it. The agency inbox and automation activity page showed the resulting decision.

| Verified local operation | PostgreSQL event | n8n execution | Delivered inbox rows |
|---|---|---:|---:|
| Scheduled overdue reminder | `f634c625-7922-5f82-a65f-57a5ec47701f` | Schedule **57**, delivery **58** | 1 |
| Revision 2 released across worker restart | `5585e969-72d5-4e93-9167-fa7e20d995b1` | **61** | 2 |
| Client requested changes to revision 2 | `96504cdc-5f92-4406-9ce9-0d0615b8cf4f` | **62** | 2 |
| Revision 3 released | `63de8a6d-6ca7-4840-8dd5-30c614536cac` | **63** | 2 |
| Client approved revision 3 | `33d9f1a4-9ca7-4432-9076-82d399bce6d3` | **64** | 2 |

The verification script matched each event, completed run, processing receipt and recipient rows to the workflow ID and successful execution in n8n's own database. Approval-event checks included the exact revision UUID. Reminder verification followed the reservation to its originating timer execution. CP2 lead and assignment and CP3 analysis, strategy and planning workflows also ran during the final browser suite.

**Limits and handoff.** Tests used fixture AI (`fixture-v1`), local file storage and the development inbox. Gmail, Telegram, Drive and a live LLM were not exercised. Local Compose runs the schedule every minute. Operators can configure a daily cron expression and timezone. Monitoring displays the latest attempt for up to 100 recent events. No outstanding CP4 verification blockers. The local baseline is `c28175d`. CP4 changes are in the working tree. No remote, push, volume reset or CP5 implementation.

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
