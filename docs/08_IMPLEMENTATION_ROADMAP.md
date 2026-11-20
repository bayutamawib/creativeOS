# CREATIVE OS — Implementation Roadmap

**Document:** Implementation Roadmap  
**Version:** 1.0  
**Status:** Proposed  
**Execution Environment:** Antigravity + Codex  
**Delivery Target:** Integrated Working MVP  
**Development Strategy:** Incremental Vertical Slices

---

## 1. Purpose

This document defines the implementation strategy for CREATIVE OS.

It converts the product, architecture, database, API, AI, automation, and frontend specifications into a practical engineering execution plan.

The objective is to produce a functioning, integrated MVP with:

- A professional Next.js web application.
- Separate Client and Admin Portals.
- A secure FastAPI backend.
- PostgreSQL persistence.
- Modular AI services.
- n8n workflow automation.
- Human approval workflows.
- Client-specific reporting.
- Reproducible local deployment.
- Automated tests and documentation.

The project must be built incrementally.

Do not attempt to implement the entire system in a single uncontrolled coding pass.

## 2. Source of Truth

Before implementation, read:

1. `AGENTS.md`
2. `docs/01_PRODUCT_REQUIREMENTS.md`
3. `docs/02_SYSTEM_ARCHITECTURE.md`
4. `docs/03_DATABASE_DESIGN.md`
5. `docs/04_API_SPECIFICATION.md`
6. `docs/05_AI_SYSTEM_DESIGN.md`
7. `docs/06_WORKFLOW_AUTOMATION.md`
8. `docs/07_FRONTEND_UX_DESIGN.md`
9. This document.
10. `docs/09_TESTING_AND_DEPLOYMENT.md`

If specifications conflict, do not silently choose an interpretation.

Document the conflict, propose a minimal resolution, update affected specifications, and proceed only when the change preserves the agreed MVP scope.

## 3. Non-Negotiable Architectural Decisions

| Area | Decision |
|---|---|
| Frontend | Next.js App Router + TypeScript |
| Styling | Tailwind CSS + shadcn/ui |
| Backend | Python + FastAPI |
| Database | PostgreSQL + SQLAlchemy + Alembic |
| Automation | n8n |
| AI | Modular Python AI services |
| Storage | Google Drive API with development fallback |
| Notifications | Telegram and Gmail integrations |
| Local deployment | Docker Compose |
| Authentication | Secure cookie-based sessions |
| Authorization | Backend RBAC and client-level isolation |
| Client experience | Full Next.js Client Portal |
| Agency experience | Full Next.js Admin Portal |
| AI governance | Human-in-the-loop |
| Research extension | Mechanistic Interpretability A2, separate from MVP |

No Streamlit.

No unnecessary autonomous multi-agent framework.

No direct n8n writes to core business tables.

No production requirement for a paid cloud deployment.

## 4. Development Strategy

### 4.1 Vertical slice development

A vertical slice implements a complete business capability across all necessary layers.

Example:

**Public Inquiry Vertical Slice**

1. Next.js inquiry form.
2. Frontend validation.
3. FastAPI endpoint.
4. Pydantic request schema.
5. Service-layer business logic.
6. PostgreSQL persistence.
7. Outbox event creation.
8. n8n event processing.
9. Internal notification.
10. Automated tests.
11. Browser verification.

The slice is complete only when the flow works end-to-end.

### 4.2 Incremental implementation

For every milestone:

1. Review relevant specifications.
2. Implement the smallest functional increment.
3. Run formatting and static checks.
4. Run relevant tests.
5. Verify the UI and API.
6. Record the result.
7. Fix critical failures before continuing.

### 4.3 No fake completeness

Do not mark a feature complete merely because:
- A page exists.
- A button is visible.
- An API route returns static JSON.
- An n8n workflow file was exported.
- A mock AI response is displayed.
- A database model has been created.

A feature is complete when its expected behavior works and its acceptance criteria pass.

---

# Part I — Repository Foundation

## 5. Recommended Repository Structure

```text
creative-os/
├── AGENTS.md
├── README.md
├── .gitignore
├── .env.example
├── compose.yaml
├── Makefile
│
├── docs/
│   ├── 01_PRODUCT_REQUIREMENTS.md
│   ├── 02_SYSTEM_ARCHITECTURE.md
│   ├── 03_DATABASE_DESIGN.md
│   ├── 04_API_SPECIFICATION.md
│   ├── 05_AI_SYSTEM_DESIGN.md
│   ├── 06_WORKFLOW_AUTOMATION.md
│   ├── 07_FRONTEND_UX_DESIGN.md
│   ├── 08_IMPLEMENTATION_ROADMAP.md
│   ├── 09_TESTING_AND_DEPLOYMENT.md
│   ├── DECISIONS.md
│   └── IMPLEMENTATION_STATUS.md
│
├── frontend/
│   ├── app/
│   ├── components/
│   ├── features/
│   ├── hooks/
│   ├── lib/
│   ├── types/
│   ├── package.json
│   └── Dockerfile
│
├── backend/
│   ├── app/
│   ├── alembic/
│   ├── tests/
│   ├── pyproject.toml
│   ├── alembic.ini
│   └── Dockerfile
│
├── automation/
│   ├── README.md
│   ├── n8n/
│   └── examples/
│
├── research/
│   └── mechanistic_interpretability/
│
├── scripts/
│   ├── seed_demo.py
│   └── smoke_test.sh
│
└── .github/
    └── workflows/
        └── ci.yml
```

This structure may be refined when justified, but the project must remain understandable to another engineer.

## 6. Required Developer Commands

Provide simple commands for common operations.

Suggested Makefile targets:

```makefile
up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	docker compose exec backend alembic upgrade head

test-backend:
	docker compose exec backend pytest

lint-frontend:
	docker compose exec frontend npm run lint

seed:
	docker compose exec backend python -m app.scripts.seed_demo
```

Adjust commands to match the actual implementation.

Every documented command must be tested.

Do not document commands that do not exist.

## 7. Environment Configuration

Create `.env.example` with placeholders for:

- Database credentials.
- Application secret.
- Frontend origin.
- Backend API URL.
- n8n configuration.
- Internal integration credentials.
- AI provider configuration.
- Google Drive credentials.
- Telegram bot credentials.
- Gmail credentials.

Never commit real secrets.

Local development must support a documented fallback for unavailable external integrations.

---

# Part II — Implementation Milestones

## 8. Milestone 0 — Specification Reconciliation

**Goal:** Resolve cross-document inconsistencies before building dependent functionality.

### Tasks

- Review all specifications.
- Confirm role definitions.
- Confirm resource ownership rules.
- Confirm business state transitions.
- Reconcile API endpoints and database entities.
- Define event and workflow identifiers.
- Define background execution identity.
- Define invitation storage.
- Define creative proposal approval persistence.
- Define brief versioning or immutable snapshots.
- Define report publication states.

### Required database clarifications

Review:

1. `content_approvals.decided_at` must be nullable for pending approvals.
2. `content_items.current_revision_id` must be handled safely during initial creation.
3. Client invitations require a secure persistence mechanism.
4. Outbox and processed-event tables must be added.
5. Notification deduplication must be supported.
6. AI generation idempotency must be supported.
7. Creative proposal selection and approval must be represented.
8. Report lifecycle states must be consistent.

### Deliverables

- Updated relevant specifications.
- Initial database migration plan.
- `docs/DECISIONS.md`.
- `docs/IMPLEMENTATION_STATUS.md`.

### Exit criteria

- No unresolved blocking architecture conflicts.
- The database supports the required workflows.
- The API contract supports the required transitions.
- Codex can explain the planned end-to-end data flow.

---

## 9. Milestone 1 — Development Infrastructure

**Goal:** Run the application infrastructure locally.

### Tasks

**Backend**
- Initialize FastAPI.
- Configure settings.
- Configure database connection.
- Add health endpoints.
- Add structured logging.
- Configure Alembic.

**Frontend**
- Initialize Next.js.
- Configure Tailwind CSS.
- Install shadcn/ui.
- Define design tokens.
- Build the initial application shell.

**Infrastructure**
- Configure PostgreSQL.
- Configure n8n.
- Create Dockerfiles.
- Create Docker Compose configuration.
- Configure local environment variables.

### Deliverables

- Running Next.js application.
- Running FastAPI application.
- Running PostgreSQL.
- Running n8n.
- Working health checks.

### Exit criteria

- `docker compose up -d --build` succeeds.
- Frontend loads in the browser.
- Backend health endpoint responds.
- Database connection succeeds.
- n8n interface is accessible.
- Services can communicate through the Docker network.

---

## 10. Milestone 2 — Authentication and Authorization

**Goal:** Establish secure user identity and portal boundaries.

### Tasks

- Create user and membership models.
- Implement migrations.
- Implement password hashing.
- Implement login.
- Implement logout.
- Implement session renewal.
- Implement `/auth/me`.
- Implement agency roles.
- Implement client roles.
- Implement client ownership checks.
- Build login UI.
- Build protected portal layouts.
- Implement route-level permission handling.

### Deliverables

- Working authentication.
- Agency and client role support.
- Protected Client Portal.
- Protected Admin Portal.
- Authorization tests.

### Exit criteria

- Agency users can access permitted admin pages.
- Client users can access permitted client pages.
- Unauthorized users are rejected.
- Cross-client API access is denied.
- Session expiration is handled.
- Authentication secrets are not exposed to the browser.

---

## 11. Milestone 3 — Workflow A: Client Acquisition

**Goal:** Complete the first end-to-end vertical slice.

### Tasks

**Frontend**
- Build public inquiry form.
- Build lead management table.
- Build lead detail view.
- Build lead conversion UI.
- Build client directory.

**Backend**
- Implement inquiry endpoint.
- Implement lead models.
- Implement lead management APIs.
- Implement transactional lead conversion.
- Implement client creation.
- Implement invitation flow.

**Automation**
- Implement outbox infrastructure.
- Implement event dispatcher.
- Implement lead-created n8n workflow.
- Implement internal notification.
- Implement workflow run tracking.

### Deliverables

- Functional inquiry-to-lead process.
- Lead conversion.
- Client creation.
- Notification workflow.
- First complete vertical slice.

### Exit criteria

A user can submit an inquiry, the agency can review it, convert it into a client, and initiate client onboarding.

The lead-created event is recorded and processed without duplicating the lead.

---

## 12. Milestone 4 — Projects and Tasks

**Goal:** Build the operational foundation for agency work.

### Tasks

- Implement project models and APIs.
- Implement project memberships.
- Implement milestones.
- Implement tasks.
- Implement task assignments.
- Build admin project pages.
- Build task management UI.
- Build client-safe project views.
- Implement project progress calculation.
- Implement task assignment notification.

### Deliverables

- Project management.
- Task management.
- Milestone tracking.
- Client project visibility.
- Assignment notification.

### Exit criteria

Agency users can create projects, assign team members, create tasks, and update project progress.

Clients can see their own projects without accessing internal task details.

---

## 13. Milestone 5 — Creative Briefs and File Management

**Goal:** Enable clients to submit structured creative requirements.

### Tasks

- Implement brief models and APIs.
- Implement brief status transitions.
- Implement approved brief snapshots.
- Implement file metadata.
- Implement Google Drive storage adapter.
- Implement local development storage fallback.
- Build guided brief submission form.
- Build brief review interface.
- Implement brief approval.
- Implement brief revision requests.

### Deliverables

- Client brief submission.
- Agency brief review.
- File attachment support.
- Brief approval history.

### Exit criteria

A client can submit a brief for an authorized project.

An agency user can review and approve the brief.

The approved brief is available as stable input for AI generation.

---

## 14. Milestone 6 — AI Creative Intelligence

**Goal:** Generate structured creative proposals from approved briefs.

### Tasks

**AI infrastructure**
- Implement provider adapter.
- Implement prompt registry.
- Implement structured output schemas.
- Implement generation persistence.
- Implement failure handling.
- Implement generation status polling.

**AI services**
- Brief Analyzer.
- Creative Strategist.
- Content Planner.
- Copywriting Assistant.

**Frontend**
- Build Creative Studio.
- Build generation status UI.
- Build creative proposal cards.
- Build content selection actions.

**Automation**
- Implement brief-approved workflow.
- Implement AI generation orchestration.
- Implement reviewer notification.

### Deliverables

- Working AI generation.
- Structured creative outputs.
- Generation history.
- Creative Studio.
- AI workflow integration.

### Exit criteria

An approved brief can generate structured analysis, creative directions, and content plans.

The agency can inspect the outputs and select proposals.

Invalid AI outputs do not become approved content.

---

## 15. Milestone 7 — Content Revision and Approval

**Goal:** Complete the core creative production lifecycle.

### Tasks

- Implement content items.
- Implement immutable content revisions.
- Implement internal approval records.
- Implement client review submission.
- Implement client feedback.
- Implement revision requests.
- Implement client approval.
- Build content editor.
- Build internal approval queue.
- Build client approval interface.
- Implement approval notifications.

### Deliverables

- Versioned creative deliverables.
- Internal review.
- Client review.
- Feedback and revision cycle.
- Final approved deliverable state.

### Exit criteria

The agency can generate or edit content, approve a specific revision internally, and submit it for client review.

The client can approve or request revisions.

A new revision does not inherit approval from an older revision.

---

## 16. Milestone 8 — Workflow C: Operational Automation

**Goal:** Automate recurring project coordination.

### Tasks

- Implement task assignment event.
- Implement deadline monitoring.
- Implement overdue detection.
- Implement reminder deduplication.
- Implement scheduled n8n workflow.
- Add operational activity logging.

### Deliverables

- Assignment notifications.
- Deadline reminders.
- Overdue task monitoring.
- Recorded workflow executions.

### Exit criteria

Eligible users receive appropriate notifications.

Completed tasks do not generate overdue reminders.

Duplicate scheduled runs do not create uncontrolled duplicate notifications.

---

## 17. Milestone 9 — Workflow D: Reporting and Analytics

**Goal:** Provide reliable project and agency reporting.

### Tasks

- Implement deterministic reporting queries.
- Implement report lifecycle.
- Implement Report Summarizer.
- Implement report generation endpoint.
- Implement report review and publication.
- Build client reports page.
- Build agency analytics page.
- Implement scheduled weekly reporting.
- Implement report notification.

### Deliverables

- Draft project reports.
- Human-reviewed report publication.
- Client-specific reports.
- Agency operational analytics.
- Scheduled report workflow.

### Exit criteria

A report can be generated from verified project data.

Agency users can review and publish it.

Clients can access only published reports belonging to their organization.

---

## 18. Milestone 10 — Monitoring and Quality Evaluation

**Goal:** Make the system observable and measurable.

### Tasks

- Build workflow monitoring UI.
- Add workflow failure details.
- Add eligible retry actions.
- Add AI generation monitoring.
- Create synthetic AI evaluation dataset.
- Implement schema validity metrics.
- Implement generation success metrics.
- Add human quality scoring rubric.
- Implement API integration tests.
- Review application logs and errors.

### Deliverables

- Automation monitoring.
- AI activity monitoring.
- Evaluation scripts.
- Evaluation results.
- Reliability improvements.

### Exit criteria

Agency managers can inspect workflow failures.

AI generation performance can be measured.

Evaluation results are reproducible and based on actual executions.

---

## 19. Milestone 11 — End-to-End Verification and Polish

**Goal:** Prepare the MVP for a professional portfolio demonstration.

### Tasks

- Run all automated tests.
- Verify all four workflows.
- Verify role permissions.
- Verify cross-client isolation.
- Verify error states.
- Verify responsive layouts.
- Verify accessibility basics.
- Remove broken placeholder actions.
- Review secrets and environment configuration.
- Improve loading and empty states.
- Prepare demonstration data.
- Document known limitations.

### Deliverables

- Verified working MVP.
- Updated README.
- Demonstration instructions.
- Screenshots.
- Architecture diagram.
- Test summary.
- Known limitations.

### Exit criteria

A reviewer can follow the complete journey:

Inquiry → Client Onboarding → Project → Brief → AI Generation → Internal Review → Client Approval → Task Tracking → Reporting.

The journey must work without manually editing database records.

---

# Part III — Research Extension

## 20. Milestone 12 — Mechanistic Interpretability

**Priority:** After the core MVP.

**Goal:** Demonstrate an independent AI research experiment.

### Tasks

- Select a small open-weight model.
- Prepare synthetic prompt pairs.
- Collect activations.
- Implement controlled comparisons.
- Train a probe or conduct activation patching.
- Evaluate results.
- Generate visualizations.
- Write research report.

### Deliverables

- Research scripts.
- Synthetic dataset.
- Experiment results.
- Visualizations.
- Research report.

### Exit criteria

The experiment is reproducible and its limitations are documented.

This milestone must not block production MVP completion.

---

# Part IV — Engineering Standards

## 21. Backend Standards

Use:
- Python type hints.
- Pydantic schemas.
- SQLAlchemy ORM.
- Alembic migrations.
- Service-layer business logic.
- Dependency-based authorization.
- Structured logging.
- Pytest.

Avoid:
- Business logic embedded entirely in API route handlers.
- Raw SQL assembled from untrusted input.
- Hardcoded credentials.
- Unvalidated external payloads.
- Direct database access from n8n.

## 22. Frontend Standards

Use:
- TypeScript.
- Next.js App Router.
- Tailwind CSS.
- shadcn/ui.
- Typed API clients.
- Accessible forms.
- Reusable feature components.
- Responsive layouts.

Avoid:
- Streamlit.
- Large monolithic page components.
- Fake functionality.
- Unnecessary global state.
- Client-side-only authorization.

## 23. Database Standards

- Use migrations for schema changes.
- Use foreign keys and appropriate constraints.
- Enforce uniqueness where required.
- Use transactions for multi-step business operations.
- Preserve historical revisions.
- Avoid destructive schema changes without a migration strategy.

## 24. Automation Standards

- Version-control n8n workflow exports.
- Use authenticated service calls.
- Use stable event IDs.
- Implement idempotency.
- Track workflow execution.
- Apply bounded retries.
- Avoid storing secrets in workflow exports.

## 25. AI Standards

- Version prompts.
- Validate structured output.
- Record generation metadata.
- Preserve human approval.
- Track failures.
- Use synthetic evaluation data.
- Avoid unsupported performance claims.

---

# Part V — Codex Execution Protocol

## 26. One Milestone at a Time

Codex must not attempt to implement all milestones in one response or execution cycle.

For each milestone:

1. Read the relevant specifications.
2. Inspect the existing repository.
3. Produce a concise implementation plan.
4. Identify files to create or modify.
5. Implement the milestone.
6. Run relevant tests.
7. Fix detected failures.
8. Update implementation status.
9. Summarize completed work and remaining issues.

Continue to the next milestone only after the current milestone's exit criteria are satisfied.

## 27. Implementation Status Tracking

Maintain:

`docs/IMPLEMENTATION_STATUS.md`

Suggested format:

```markdown
# CREATIVE OS — Implementation Status

## Current Milestone
Milestone 1 — Development Infrastructure

## Status
In Progress

## Completed
- [x] FastAPI initialized
- [x] PostgreSQL configured

## Remaining
- [ ] Next.js application shell
- [ ] n8n configuration
- [ ] Docker Compose verification

## Tests
- Backend health: PASS
- Database connection: PASS
- Frontend startup: NOT RUN

## Blockers
None

## Next Action
Complete frontend initialization.
```

Never mark tests as passed without executing them.

## 28. Architecture Decision Log

Maintain:

`docs/DECISIONS.md`

Example:

```markdown
# Architecture Decisions

## ADR-001 — Authentication Strategy

Status: Accepted

Decision:
Use secure cookie-based authentication.

Rationale:
Supports browser-based portals without exposing
long-lived tokens to JavaScript.

Consequences:
Requires CSRF protection and secure cookie configuration.
```

Record meaningful architectural decisions, not every minor code change.

## 29. Definition of Done

A milestone is complete only when:

- Required functionality is implemented.
- Relevant tests pass.
- No critical authorization failures remain.
- Database migrations work.
- UI actions perform real operations.
- Error handling is implemented.
- Documentation is updated.
- Known limitations are recorded.

A screenshot or successful compilation alone is not sufficient.

## 30. Testing Gates

Before advancing:

**Backend gate**
- Relevant unit tests pass.
- API integration tests pass.
- Authorization tests pass where applicable.

**Frontend gate**
- TypeScript checks pass.
- Linting passes.
- Relevant UI interactions work.

**Database gate**
- Migrations apply successfully.
- Constraints are verified.

**Automation gate**
- Workflow execution is tested.
- Duplicate processing is handled.
- Failure behavior is verified.

**Security gate**
- No committed secrets.
- No unauthorized cross-client access.
- No internal data exposure through client APIs.

## 31. Blocker Handling

If implementation is blocked by:
- Missing API credentials.
- Unavailable external service.
- Unsupported local dependency.
- Unresolved architectural conflict.

Codex should:

1. Document the blocker.
2. Identify the affected functionality.
3. Implement a safe local fallback where appropriate.
4. Preserve the production integration interface.
5. Continue independent work where possible.
6. Never claim the blocked integration is functioning.

Examples:

- Missing Telegram token → use a development notification adapter.
- Missing Google Drive credentials → use local storage adapter.
- Missing LLM API key → use deterministic test fixtures for automated tests.

A fallback is not equivalent to verified production integration.

---

# Part VI — Demonstration Strategy

## 32. Synthetic Demo Environment

Create synthetic demonstration data.

Suggested:
- One agency organization.
- Two client organizations.
- Three agency users.
- Two client users per client.
- Several projects.
- Multiple creative briefs.
- Example content revisions.
- Tasks and milestones.
- Sample workflow executions.
- Sample reports.

All data must be fictional.

## 33. Demo User Journey

The final demonstration should show:

1. Public visitor submits an inquiry.
2. Agency manager reviews the lead.
3. Agency manager converts the lead.
4. Client account is invited.
5. Agency creates a project.
6. Client submits a creative brief.
7. Agency approves the brief.
8. AI generates creative proposals.
9. Agency selects and edits a proposal.
10. Agency approves a content revision.
11. Client reviews the deliverable.
12. Client requests a revision or approves it.
13. Agency tracks project tasks.
14. Workflow automation sends notifications.
15. Agency generates a report.
16. Client views the published report.

The demo must use the actual application interfaces and APIs.

## 34. Portfolio Documentation

The final README should include:
- Project overview.
- Business problem.
- Solution architecture.
- Technology stack.
- Four integrated workflows.
- AI system design.
- Human-in-the-loop approach.
- Security considerations.
- Local setup.
- Screenshots.
- Demo instructions.
- Evaluation approach.
- Known limitations.
- Research extension overview.

Do not claim production deployment, real client adoption, or measured business improvements without supporting evidence.

---

## 35. Final MVP Acceptance Criteria

CREATIVE OS is considered a working MVP when:

1. The application runs locally through documented commands.
2. Client and Admin Portals function.
3. Authentication and authorization work.
4. Client data is isolated.
5. Public inquiry and lead conversion work.
6. Project and task management work.
7. Client brief submission works.
8. AI creative generation works with a configured provider.
9. Structured outputs are validated.
10. Human approval controls client-facing content.
11. Revision history is preserved.
12. n8n workflows execute reliably.
13. Notifications are integrated or explicitly documented as development fallbacks.
14. Reports use verified metrics.
15. Workflow monitoring is available.
16. Critical automated tests pass.
17. The end-to-end demo journey is reproducible.
18. Documentation accurately reflects the implemented system.

---

## 36. Instructions for Codex

You are responsible for implementing CREATIVE OS according to the approved specifications.

Start with Milestone 0.

Do not skip specification reconciliation.

Do not implement the entire system at once.

For every milestone:
- Plan.
- Implement.
- Test.
- Verify.
- Document.
- Report.

Use the existing specifications as the source of truth.

Preserve:
- FastAPI business ownership.
- Client data isolation.
- Human approval.
- Reliable event delivery.
- Structured AI outputs.
- Professional Next.js user experience.

Prioritize a fully working integrated MVP over unnecessary features.

**The final deliverable must be a functional engineering project, not merely a collection of generated source files.**