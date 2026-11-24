# CREATIVE OS — Codex Handoff

## Current status

CP0–CP8-B are implemented locally. CP8-A added authorized image galleries, thumbnails, previews, and revision media UX. CP8-B added private MP4 upload, optional manual covers, fallback artwork and play indicators, HTML5 playback, authenticated HTTP Range streaming, seeking, fullscreen, and video-based client approval. Automated verification and main-stack owner acceptance preparation were completed. Manual CP8-B owner acceptance remains pending. Do not begin CP9.

The main Compose application is intended to remain on `fixture / fixture-v1`. The main PostgreSQL database has been migrated to `0015_video_cover`. Existing data and volumes must be preserved.

## Phase 1 findings: Creative Studio AI quality audit

The generic Orchard creative direction came from the deterministic fixture, not a live Groq response. The approved snapshot contained only the objective, “Launch a fictional orchard collection.” Target audience, key message, tone, content type, restrictions, additional context, and brand guidance were empty.

`backend/app/ai/providers.py` hard-codes fixture phrases including “Audience not specified,” “Clear and direct,” “Project introduction,” and the “First look” visual direction. It uses the objective as the fallback key message.

All four Creative Studio capabilities share the compatible Chat Completions provider and can technically run through Groq without architecture changes:

1. Brief Analyzer — live Groq unverified.
2. Creative Strategist — live Groq unverified.
3. Content Planner — live Groq unverified.
4. Copywriting Assistant — one controlled synthetic Groq request passed in CP7.

Pydantic validates strict JSON structure. Production validation also enforces plan count and permitted channels. It does not prove factual grounding, distinctiveness, non-duplication, or editorial usefulness. Main risks are invented audience or brand facts, generic directions, duplicate plan ideas, inconsistent outputs, and schema failures.

## Approved Phase 2A isolation plan

Use a separate source copy, Compose project name, ports, database, volumes, and synthetic accounts. Keep the main stack unchanged on fixture mode. Prepare one detailed fictional brief and run the intended sequence later: analysis → strategy → human direction selection → plan → human plan-item selection → copywriting.

Before any live request, stop the isolated continuous worker and n8n, confirm zero pending or running generations, and use one-shot runner execution. Inspect each persisted job before allowing the next stage. Preserve redacted inputs, outputs, parameters, provider/model, prompt version, token usage, latency, errors, and selected proposal IDs. A timeout must be reconciled before retrying.

## Phase 2B setup tasks — no live API calls

1. Inspect current Git status and preserve every existing modification, including the owner’s untracked `cek_groq.py`.
2. Create an isolated working copy with `rsync`, excluding `.git`, `.env`, `.local`, `node_modules`, `.next`, caches, credentials, and generated screenshots.
3. Run `scripts/init_env.py` only inside the isolated copy. Assign unused ports and a unique `COMPOSE_PROJECT_NAME`. Keep `AI_PROVIDER=fixture`, `AI_MODEL=fixture-v1`, and `FILE_PROVIDER=local` during setup.
4. Start and seed only the isolated stack. Verify health and confirm it uses separate volumes. Do not touch the main Compose project.
5. Create one detailed synthetic brief for fictional Morrow Orchard: autumn fruit box, home cooks in a fictional service area, fictional waitlist goal, seasonal-variety message, warm observant tone, Instagram and Website, three content items, and available fruit/packing/recipe-card imagery. Explicitly prohibit claims about price, nutrition, certification, delivery dates, testimonials, and other unknown facts.
6. Submit and approve the synthetic brief while still in fixture mode. Record its project, brief, and approved snapshot IDs.
7. Prepare a redacted evidence directory and scoring rubric for relevance, specificity, grounding, distinctiveness, and actionability. Do not store credentials or raw authorization headers.
8. Confirm the isolated queue state, stop its worker and n8n, and document the exact four planned live jobs and expected dependencies.
9. Prepare the environment-variable names and one-shot commands for Groq, but do not load credentials into files and do not execute the commands.

## Relevant files and commands

- `docs/LOCAL_OPERATIONS.md` — CP7 isolation and one-shot provider procedure.
- `docs/IMPLEMENTATION_STATUS.md` — CP7 evidence and current checkpoint status.
- `docs/DECISIONS.md` — ADR-034 and ADR-035 live-provider boundaries.
- `backend/app/ai/providers.py` — fixture and compatible provider.
- `backend/app/ai/contracts.py` — prompts, schemas, temperatures, validation.
- `backend/app/ai/runner.py` — durable one-shot execution.
- `backend/app/services/studio.py` and `backend/app/api/studio.py` — stage sequencing and API.
- `scripts/init_env.py`, `scripts/seed_local.py`, and `scripts/smoke.py` — isolated setup.

Expected setup command families: `mktemp -d`, scoped `rsync`, isolated `python3 scripts/init_env.py`, isolated `docker compose up --build -d --wait`, `python3 scripts/seed_local.py`, and `python3 scripts/smoke.py`. Resolve unique ports before startup. Never echo secret values.

## Critical safety constraints

- Phase 2B performs setup only. Make no live Groq or other LLM request.
- Keep the main stack, database, volumes, configuration, and generated data unchanged.
- Use synthetic data only. Do not send customer or real brand information.
- Do not modify production prompts, schemas, provider architecture, or application behavior.
- Do not expose keys in Git, chat, screenshots, logs, shell history, evidence, or Compose files.
- Do not leave a live-configured continuous worker or n8n running.
- Do not commit, push, deploy, reset, or discard existing work.

## Git and stopping point

The working tree contains uncommitted CP8-A/CP8-B code, documentation, tests, fixtures, screenshots, and `cek_groq.py`. Treat all as owner work. Do not overwrite, delete, stage, or commit it.

**Stop Phase 2B after the isolated fixture stack, synthetic approved snapshot, empty/stopped queue, redacted evidence template, and unexecuted live-command checklist are ready. Report identifiers and readiness, then request explicit owner approval before loading live credentials or executing the first Groq Brief Analyzer request.**

## Additional safety checks and Phase 2B acceptance criteria

### Pre-execution safety checks

1. Before running `scripts/smoke.py` or any setup command, inspect its side effects. Confirm it cannot trigger external LLM requests or modify the main stack.
2. Before starting isolated containers, inspect the resolved `docker compose config`. Verify unique project name, host ports, database volumes, bind mounts, and container identities. Confirm no unintended resource sharing with the main stack.
3. If isolation checks, migrations, seeding, or startup fail, stop and report the issue. Do not perform destructive cleanup, reset volumes, or retry state-changing commands without owner approval.

### Phase 2B acceptance criteria

Phase 2B is complete only when all conditions below are verified:

- Isolated stack is healthy.
- Main stack, database, volumes, and configuration remain unchanged.
- Synthetic Morrow Orchard brief has been submitted and approved.
- Approved snapshot ID is recorded.
- No pending or running AI generation jobs exist in the isolated queue.
- Isolated continuous worker and n8n are stopped.
- Redacted evidence directory and evaluation rubric are ready.
- Zero live Groq or other external LLM requests have been executed.

Stop and request owner approval before loading live credentials or executing any Groq generation.