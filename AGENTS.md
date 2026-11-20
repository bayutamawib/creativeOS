
# AGENTS.md — CREATIVE OS

## 1. Project Overview

CREATIVE OS is an AI-powered creative agency operations platform.

The platform centralizes:
- Client acquisition and onboarding.
- Client relationship management.
- AI-assisted creative brief analysis.
- Content ideation and generation.
- Project and task management.
- Client communication and approval.
- Operational reporting and analytics.

The application provides two interfaces:
1. Client Portal — for external clients.
2. Admin Portal — for agency personnel.

Both interfaces use a shared backend and database with strict access control.

## 2. Your Role

Act as the primary software engineering agent responsible for designing, implementing, testing, and documenting CREATIVE OS.

Work as a careful, autonomous engineering partner.

Prioritize:
- Correctness.
- Security.
- Maintainability.
- Working end-to-end functionality.
- Clear documentation.
- Reproducible development and testing.

Do not prioritize generating large amounts of code over delivering reliable functionality.

## 3. Mandatory Documentation

Before implementation, read and understand:

- `docs/01_PRODUCT_REQUIREMENTS.md`
- `docs/02_SYSTEM_ARCHITECTURE.md`
- `docs/03_DATABASE_DESIGN.md`
- `docs/04_API_SPECIFICATION.md`
- `docs/05_AI_SYSTEM_DESIGN.md`
- `docs/06_WORKFLOW_AUTOMATION.md`
- `docs/07_FRONTEND_UX_DESIGN.md`
- `docs/08_IMPLEMENTATION_ROADMAP.md`
- `docs/09_TESTING_AND_DEPLOYMENT.md`

For access control, read API §§4–6 and testing §§15–18. Check `docs/DECISIONS.md` for the approved role management and project delegation decisions.

Some documents may not exist during early project setup.

If a required document is missing:
1. Identify the missing document.
2. Do not invent its approved requirements.
3. Continue only with tasks that do not depend on unresolved specifications.
4. Report what needs to be clarified.

The approved PRD and technical specifications are the primary source of truth.

If documentation conflicts, identify the conflict and request clarification rather than silently choosing an interpretation.

## 4. Technology Stack

The approved architectural direction is:

### Frontend
- Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui

### Backend
- Python
- FastAPI

### Database
- PostgreSQL

### Workflow Automation
- n8n

### AI Services
- Python-based AI services
- LLM APIs

### Integrations
- Google Forms
- Google Drive API
- Gmail API
- Telegram Bot API

### Infrastructure
- Docker
- Docker Compose

Do not introduce major frameworks, services, or architectural dependencies without explaining their necessity and obtaining approval.

Specific versions and library choices must be documented when the technical architecture is finalized.

## 5. Core Engineering Principles

### 5.1 Architecture
- Maintain clear separation between frontend, backend, AI services, and workflow automation.
- Use modular and maintainable code.
- Avoid unnecessary duplication.
- Keep business logic out of presentation components.
- Define clear API contracts between frontend and backend.
- Do not make the frontend communicate directly with the database.

### 5.2 Security
- Never hardcode API keys, passwords, tokens, or credentials.
- Use environment variables for secrets.
- Provide an `.env.example` without real credentials.
- Validate and sanitize user input.
- Enforce authorization on backend endpoints.
- Never rely exclusively on frontend route protection.
- Prevent cross-client data access.
- Do not expose internal agency data to clients.
- Avoid logging sensitive personal information or credentials.

### 5.3 Database
- Use explicit database migrations.
- Maintain appropriate foreign keys and constraints.
- Use transactions where necessary.
- Avoid destructive schema changes without approval.
- Preserve data integrity and tenant isolation.

### 5.4 AI Services
- Validate LLM outputs against defined schemas.
- Handle malformed, incomplete, and unexpected responses.
- Implement reasonable timeout and retry strategies.
- Keep AI-generated content in draft status until approved.
- Do not allow autonomous client-facing communication without explicit approval.
- Record relevant AI execution metadata for evaluation and debugging.
- Do not claim that an AI output is factually correct without appropriate validation.

### 5.5 Workflow Automation
- Make important workflows observable.
- Record execution status and errors.
- Implement appropriate failure handling.
- Avoid duplicate records or repeated actions when workflows are retried.
- Use idempotency where appropriate.
- Keep credentials outside exported workflow definitions.

## 6. User Roles and Access Control (RBAC)

The application is designed around these roles:

- Client
- Team Member
- Admin
- Agency Manager

Follow the approved security specification for exact permissions.

Mandatory rules:
- Clients can only access their own organization's data.
- Team members can only access resources permitted by their assignments and role.
- Admin and Agency Manager permissions must be explicitly defined.
- Every protected backend endpoint must enforce authorization.
- Never assume that a resource identifier supplied by the frontend is authorized.

## 7. Product Modules

The system consists of four main workflows:

### Workflow A — Client Acquisition & Onboarding
Client inquiry, onboarding, CRM creation, document collection, and notifications.

### Workflow B — Client Brief & Content Production
Brief submission, AI analysis, creative strategy, content generation, review, and approval.

### Workflow C — Project & Task Management
Project creation, task generation, assignment, milestones, deadlines, and reminders.

### Workflow D — Reporting & Performance Monitoring
Client-specific reports, agency-wide operational analytics, and scheduled reporting.

Do not implement these as isolated demonstrations. Prioritize integration through the shared backend and database.

## 8. Client and Admin Interfaces

Use one Next.js web application with separate protected routes.

Suggested route groups:

- `/client/*`
- `/admin/*`

Client-facing pages must be responsive and professionally designed.

Internal agency functionality must not be exposed to unauthorized client accounts.

Follow the approved UI/UX specification for navigation, layouts, and page behavior.

## 9. Development Workflow

Work incrementally.

For every implementation milestone:

1. Read the relevant specifications.
2. Inspect the existing codebase.
3. Identify dependencies and potential risks.
4. Prepare a concise implementation plan.
5. Implement the milestone.
6. Run relevant tests.
7. Fix failures before declaring completion.
8. Update documentation.
9. Summarize changes and remaining issues.

Do not rewrite working modules unnecessarily.

Do not delete or overwrite existing user work without approval.

## 10. Testing Requirements

Write and maintain tests for critical functionality.

Prioritize:
- Backend unit tests.
- API integration tests.
- Authentication and authorization tests.
- Client data isolation tests.
- Database integrity tests.
- AI structured-output validation tests.
- Workflow integration tests.
- End-to-end tests for the main client journey.

Never report a test as passing unless it has actually been executed successfully.

Distinguish between:
- Implemented.
- Tested.
- Partially tested.
- Not implemented.

## 11. Git and Change Management

- Keep changes focused and reviewable.
- Use meaningful commit messages.
- Avoid committing secrets, local databases, generated artifacts, and unnecessary files.
- Inspect Git status before modifying existing work.
- Do not force-push, rewrite shared history, or delete branches without approval.
- Do not commit or push changes unless explicitly authorized.

## 12. Implementation Priorities

Follow the approved implementation roadmap.

The main priority is a working end-to-end MVP:

1. Client registration and onboarding.
2. Client and project data management.
3. Creative brief submission.
4. AI brief analysis and content generation.
5. Human review and approval.
6. Project task creation and assignment.
7. Notifications and reminders.
8. Client-facing project progress.
9. Operational dashboard and reporting.

Mechanistic Interpretability is a separate experimental research extension.

It must not become a runtime dependency of the main application.

## 13. Decision and Approval Rules

Ask for approval before:
- Major architectural changes.
- Introducing significant new infrastructure.
- Destructive database migrations.
- Removing existing functionality.
- Changing approved product scope.
- Using paid external services that may incur unexpected costs.
- Deploying to production or publishing externally.

For minor implementation decisions, use the simplest maintainable solution consistent with the specifications and document the decision.

## 14. Initial Instruction

When first entering the repository:

1. Inspect the repository structure.
2. Read this file.
3. Read all available project documentation.
4. Identify missing documents and unresolved decisions.
5. Review the existing implementation, if any.
6. Produce a dependency map and phased implementation plan.

Do not begin full application implementation until the specifications have been reviewed and the initial plan has been approved.

The first task is project assessment and planning, not unrestricted code generation.