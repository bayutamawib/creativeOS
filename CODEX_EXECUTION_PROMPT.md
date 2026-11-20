# CREATIVE OS — Codex Master Execution Prompt

**File:** `CODEX_EXECUTION_PROMPT.md`  
**Version:** 1.0  
**Purpose:** End-to-End Implementation Instructions  
**Execution Agent:** Codex in Antigravity  
**Project:** CREATIVE OS — AI-Powered Creative Agency Operations Platform

---

## 1. Your Mission

You are the lead software engineer responsible for implementing CREATIVE OS from its approved technical specifications.

Your objective is to transform the documented architecture into a fully functioning, integrated, locally deployable MVP.

CREATIVE OS is a creative agency operations platform that integrates:

- Client acquisition and onboarding.
- AI-assisted creative production.
- Project and task management.
- Client approvals and revision management.
- Workflow automation.
- Agency and client reporting.

The system must demonstrate real engineering capabilities in:

- AI application development.
- Backend engineering.
- API design.
- System integration.
- Workflow automation.
- Database engineering.
- Full-stack web development.
- Security and authorization.
- Testing and observability.

You are expected to implement working functionality, not merely generate source files or mock interfaces.

## 2. Read the Project Specifications

Before writing application code, inspect the repository and read the following files in order:

```text
AGENTS.md

docs/01_PRODUCT_REQUIREMENTS.md
docs/02_SYSTEM_ARCHITECTURE.md
docs/03_DATABASE_DESIGN.md
docs/04_API_SPECIFICATION.md
docs/05_AI_SYSTEM_DESIGN.md
docs/06_WORKFLOW_AUTOMATION.md
docs/07_FRONTEND_UX_DESIGN.md
docs/08_IMPLEMENTATION_ROADMAP.md
docs/09_TESTING_AND_DEPLOYMENT.md
```

Treat these documents as the project specification baseline.

Do not rely on assumptions about earlier ChatGPT conversations.

If a required document is missing, report it before implementing functionality that depends on it.

## 3. Non-Negotiable Technology Stack

Use the following technologies:

| Layer | Technology |
|---|---|
| Frontend | Next.js App Router |
| Language | TypeScript |
| Styling | Tailwind CSS |
| Components | shadcn/ui |
| Backend | Python + FastAPI |
| ORM | SQLAlchemy |
| Database | PostgreSQL |
| Migrations | Alembic |
| Automation | n8n |
| AI | Modular Python services |
| Validation | Pydantic |
| Containers | Docker Compose |
| Backend tests | Pytest |
| Frontend tests | Vitest |
| E2E tests | Playwright |
| CI | GitHub Actions |

Do not introduce Streamlit.

Do not introduce Kubernetes, a large autonomous multi-agent framework, or unnecessary microservices.

Do not require paid cloud infrastructure for the local MVP.

## 4. Required Business Workflows

### Workflow A — Client Acquisition & Onboarding

Implement:

Public Inquiry → Lead Management → Agency Qualification → Lead Conversion → Client Onboarding → Project Creation.

### Workflow B — AI Creative Intelligence

Implement:

Client Brief → Agency Approval → AI Brief Analysis → Creative Direction → Content Plan → Copywriting → Internal Review → Client Review → Approval or Revision.

### Workflow C — Project & Task Management

Implement:

Project Creation → Milestones → Tasks → Assignments → Deadline Monitoring → Notifications → Client-Safe Progress.

### Workflow D — Reporting & Monitoring

Implement:

Verified Project Metrics → AI-Assisted Report Summary → Agency Review → Report Publication → Client Portal.

All four workflows must operate through the same application and database.

## 5. Required User Interfaces

Build one Next.js application with:

**Client Portal**
- Dashboard.
- Projects.
- Briefs.
- Approvals.
- Reports.
- Files.

**Admin Portal**
- Dashboard.
- Leads.
- Clients.
- Projects.
- Tasks.
- Creative Studio.
- Approvals.
- Automation Monitoring.
- Analytics.
- Settings.

The UI must be responsive, polished, accessible, and connected to real backend functionality.

Do not use static placeholder pages as substitutes for working features.

## 6. Architecture Boundaries

### FastAPI

FastAPI is the authority for:
- Authentication.
- Authorization.
- Business logic.
- State transitions.
- Database transactions.
- Client ownership.
- Content approvals.
- Report publication.

### n8n

n8n handles:
- Event-driven orchestration.
- Scheduled jobs.
- External notifications.
- Integration coordination.
- Workflow execution reporting.

n8n must not directly mutate core business tables.

### AI Services

AI services handle:
- Brief analysis.
- Creative direction.
- Content planning.
- Copywriting.
- Report summarization.

AI outputs must be validated, persisted, and reviewed by humans before client-facing publication.

### PostgreSQL

PostgreSQL is the authoritative business data store.

Use migrations for all schema changes.

## 7. Execution Strategy

Follow the implementation milestones in:

`docs/08_IMPLEMENTATION_ROADMAP.md`

Start with **Milestone 0 — Specification Reconciliation**.

Do not skip directly to frontend implementation or AI generation.

For every milestone:

1. Inspect the current repository.
2. Identify relevant specifications.
3. Prepare a concise implementation plan.
4. Implement the required functionality.
5. Run relevant checks and tests.
6. Fix critical failures.
7. Verify acceptance criteria.
8. Update implementation status.
9. Proceed when the milestone is complete.

You may continue automatically to subsequent milestones when all required verification gates pass and no user decision is needed.

Do not advance past unresolved critical failures.

## 8. Milestone 0 — Immediate First Task

Your first task is to reconcile the specifications.

Inspect and resolve:

- Database and API inconsistencies.
- Approval state definitions.
- Creative proposal persistence.
- Brief versioning.
- Client invitation storage.
- AI generation lifecycle.
- Asynchronous execution.
- System execution identity.
- Workflow event delivery.
- Outbox and idempotency tables.
- Notification deduplication.
- Report lifecycle.
- Cross-client authorization boundaries.

Create or update:

```text
docs/DECISIONS.md
docs/IMPLEMENTATION_STATUS.md
```

Update existing specifications where necessary.

Prefer the smallest coherent solution that preserves the approved product scope.

If a decision materially changes the agreed architecture, stop and request approval before proceeding.

## 9. Engineering Standards

### Backend

- Use Python type hints.
- Use Pydantic request and response schemas.
- Use SQLAlchemy models.
- Use Alembic migrations.
- Keep business logic in service modules.
- Enforce authorization at backend boundaries.
- Use structured error handling.
- Write automated tests.

### Frontend

- Use TypeScript.
- Use reusable components.
- Use typed API clients.
- Implement responsive layouts.
- Implement loading and error states.
- Use accessible controls.
- Preserve separate Client and Admin experiences.

### AI

- Use a provider abstraction.
- Version prompt templates.
- Validate structured output.
- Persist generation metadata.
- Handle failures.
- Enforce human review.
- Support fixture-based testing.

### Automation

- Use authenticated service calls.
- Implement event idempotency.
- Use a transactional outbox.
- Record workflow executions.
- Apply bounded retries.
- Export n8n workflows to version-controlled JSON files.

## 10. Security Requirements

You must enforce:

- Secure authentication.
- Role-based authorization.
- Client-level data isolation.
- CSRF protection where applicable.
- Secure file access.
- Safe handling of external inputs.
- Protection against prompt injection.
- Secrets management.
- Human approval for client-facing content.

Never expose API keys, tokens, passwords, or internal service credentials in frontend code or committed files.

Never assume a client is authorized merely because they know a resource UUID.

## 11. Local Development Requirements

The application must run locally using Docker Compose.

Expected services:

```text
frontend
backend
postgres
n8n
worker or event dispatcher
```

Provide:

- `.env.example`
- Dockerfiles.
- Compose configuration.
- Database migrations.
- Demo seed script.
- Health checks.
- Setup instructions.
- Smoke test script.

The application should remain demonstrable without paid cloud infrastructure.

## 12. External Integration Fallbacks

Some credentials may not be available during development.

Support safe development adapters:

| Integration | Development fallback |
|---|---|
| LLM provider | Fixture-based provider |
| Telegram | Logged development notifications |
| Gmail | Development email adapter |
| Google Drive | Local file storage adapter |
| Google Forms | Native inquiry form |

Fallbacks must preserve the expected interface.

Clearly identify when a fallback is active.

Do not claim live integrations are working unless they have been verified.

## 13. Testing Requirements

After each milestone, execute relevant tests.

Required categories:

- Backend unit tests.
- API integration tests.
- Database migration tests.
- Frontend component tests.
- Authorization tests.
- Cross-client isolation tests.
- AI contract tests.
- Automation idempotency tests.
- End-to-end browser tests.

Do not fabricate test results.

Do not silently remove failing tests.

If a test cannot run, document why.

## 14. Progress Tracking

Maintain:

`docs/IMPLEMENTATION_STATUS.md`

After each milestone, record:

- Current milestone.
- Completed features.
- Remaining features.
- Files changed.
- Tests executed.
- Test results.
- Known failures.
- Blockers.
- Next action.

Use clear status labels:

- Not Started.
- In Progress.
- Blocked.
- Completed.
- Verified.

A feature may be implemented without being verified.

Do not confuse these states.

## 15. Architecture Decisions

Maintain:

`docs/DECISIONS.md`

Record meaningful decisions including:

- Decision identifier.
- Context.
- Selected approach.
- Alternatives considered.
- Rationale.
- Consequences.

Do not introduce significant architectural changes without documenting them.

## 16. Human Approval Boundaries

Stop and request user approval before:

- Changing the agreed technology stack.
- Introducing a paid external service.
- Deploying publicly.
- Deleting existing user data.
- Resetting persistent databases.
- Changing repository visibility.
- Publishing private files.
- Making significant product scope changes.
- Introducing major infrastructure dependencies.

Routine implementation decisions within the approved architecture may be made autonomously.

## 17. Research Extension

Mechanistic Interpretability A2 is a separate research milestone.

Do not implement it before the core MVP is verified unless explicitly instructed.

The research extension must not become a dependency of production creative workflows.

## 18. Definition of Done

The MVP is complete only when:

1. Docker Compose starts the required services.
2. Client and Admin Portals work.
3. Authentication and authorization are verified.
4. Cross-client isolation tests pass.
5. All four workflows are integrated.
6. AI generation produces validated outputs.
7. Human approvals work correctly.
8. n8n workflows execute and record results.
9. Reporting uses verified database metrics.
10. Critical automated tests pass.
11. The end-to-end demo journey works.
12. README and setup instructions are accurate.
13. Known limitations are documented.

Do not declare the MVP complete prematurely.

## 19. Final Deliverables

Produce:

- Working source code.
- Database migrations.
- n8n workflow exports.
- AI prompt templates.
- Automated tests.
- Docker Compose setup.
- Synthetic demo data.
- Architecture documentation.
- Screenshots of implemented pages.
- Evaluation results.
- Final README.
- Implementation status report.

All deliverables must reflect actual implementation.

## 20. Initial Execution Instruction

Begin now.

Your first response should:

1. Summarize your understanding of CREATIVE OS.
2. Confirm which specification files are present.
3. Identify any blocking inconsistencies.
4. Present your Milestone 0 implementation plan.
5. Begin Milestone 0 work if the repository is accessible and no major approval is required.

After Milestone 0, continue through the implementation roadmap incrementally.

Do not ask for confirmation after every routine implementation step.

Do not skip testing.

Do not claim success without verification.

**Your mission is to deliver a functioning, integrated, reproducible CREATIVE OS MVP that demonstrates professional AI engineering and workflow automation capabilities.**