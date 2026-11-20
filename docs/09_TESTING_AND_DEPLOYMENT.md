# CREATIVE OS — Testing & Deployment Specification

**Document:** Testing & Deployment  
**Version:** 1.0  
**Status:** Proposed  
**Target:** Reproducible Local MVP  
**Environment:** Docker Compose  
**Testing:** Pytest, Vitest, Playwright  
**CI/CD:** GitHub Actions

---

## 1. Purpose

This document defines the testing, quality assurance, deployment, security verification, and demonstration requirements for CREATIVE OS.

The primary deployment target is a reproducible local environment that runs on a developer's machine without requiring paid cloud infrastructure.

The system must demonstrate four integrated business workflows:

- Workflow A — Client Acquisition & Onboarding.
- Workflow B — AI Creative Intelligence & Content Production.
- Workflow C — Project & Task Management.
- Workflow D — Reporting & Performance Monitoring.

The final MVP must be testable, observable, and reproducible.

A successfully started application is not automatically a successfully verified application.

## 2. Quality Objectives

The system must demonstrate:

1. Correct business behavior.
2. Secure authentication and authorization.
3. Client data isolation.
4. Reliable database persistence.
5. Correct AI output validation.
6. Human-controlled approval transitions.
7. Idempotent workflow automation.
8. Recoverable integration failures.
9. Functional frontend interactions.
10. Reproducible local deployment.

Testing should focus on business-critical behavior before visual polish or optional enhancements.

## 3. Testing Strategy

Use a layered testing approach.

| Test layer | Primary tool | Purpose |
|---|---|---|
| Backend unit tests | Pytest | Validate business logic |
| Backend integration tests | Pytest + HTTPX | Verify APIs and database operations |
| Frontend unit tests | Vitest | Test utility and component behavior |
| Frontend component tests | Testing Library | Verify user interactions |
| End-to-end tests | Playwright | Verify complete browser workflows |
| AI contract tests | Pytest + Pydantic | Validate structured AI outputs |
| Automation integration tests | Pytest + n8n | Verify events, retries, and workflow execution |
| Security tests | Pytest + Playwright | Verify authorization and isolation |
| Deployment smoke tests | Shell + HTTP checks | Verify running services |

Not every feature requires every test type.

Prioritize the most appropriate level for each risk.

---

# Part I — Backend Testing

## 4. Unit Tests

Unit tests should cover business rules independently from external services.

Required areas:
- Lead conversion.
- Client membership authorization.
- Project ownership.
- Task status transitions.
- Milestone progress calculations.
- Brief approval eligibility.
- Content revision handling.
- Approval state transitions.
- Report metric calculations.
- Notification deduplication.

Example:

```python
def test_completed_task_is_not_overdue():
    task = make_task(
        status="completed",
        due_date=past_date()
    )

    assert is_task_overdue(task) is False
```

This example illustrates the intended behavior; helper functions must be implemented or replaced with actual project functions.

## 5. API Integration Tests

Use HTTPX with FastAPI's ASGI application.

Tests must verify:
- Request validation.
- Response schemas.
- Authentication requirements.
- Authorization.
- Database persistence.
- Transaction behavior.
- Error responses.
- Pagination.
- Idempotency.

### 5.1 Authentication tests

Test:
- Valid login.
- Invalid credentials.
- Logout.
- Expired session.
- Missing session.
- Unauthorized endpoint access.
- CSRF protection on state-changing browser requests.
- Secure cookie configuration.

### 5.2 Lead tests

Test:
- Public inquiry creation.
- Invalid inquiry rejection.
- Duplicate submission handling.
- Authorized lead conversion.
- Duplicate conversion rejection.
- Client record creation.

### 5.3 Project tests

Test:
- Project creation.
- Project membership.
- Task creation.
- Task assignment.
- Milestone updates.
- Client-safe project responses.

### 5.4 Creative tests

Test:
- Brief submission.
- Brief approval.
- Generation eligibility.
- Content creation.
- Revision history.
- Internal approval.
- Client approval.
- Revision requests.

### 5.5 Reporting tests

Test:
- Correct metric calculations.
- Reporting-period filtering.
- Report generation.
- Draft visibility restrictions.
- Authorized publication.
- Cross-client report isolation.

## 6. Database Testing

Use an isolated PostgreSQL test database.

Do not substitute SQLite for PostgreSQL integration tests when testing PostgreSQL-specific behavior.

Verify:
- Alembic migrations.
- Foreign key constraints.
- Unique constraints.
- Nullable fields.
- Transaction rollback.
- Cascade and deletion behavior.
- Concurrent update handling.
- Client ownership relationships.

### 6.1 Migration verification

At minimum:
1. Create a clean test database.
2. Apply all migrations.
3. Verify expected tables and constraints.
4. Execute representative CRUD operations.
5. Confirm the schema matches the ORM definitions.

Rollback testing should be performed for migrations that explicitly support downgrade.

Do not assume all migrations are safely reversible.

---

# Part II — Frontend Testing

## 7. Component Tests

Use Vitest and Testing Library.

Test:
- Form validation.
- Navigation visibility.
- Status indicators.
- Approval confirmation dialogs.
- Error messages.
- Empty states.
- Loading states.
- Revision selection.
- Notification interactions.

Example:

```tsx
it("requires feedback when requesting revision", async () => {
  // Render the approval panel.
  // Select "Request Revision".
  // Submit without feedback.
  // Assert that validation prevents submission.
});
```

Use actual test fixtures and mocked API boundaries where appropriate.

## 8. End-to-End Browser Tests

Use Playwright.

E2E tests should exercise real frontend routes and backend APIs.

Recommended critical journeys:

**Journey A — Lead onboarding**
- Open public inquiry.
- Submit valid inquiry.
- Log in as agency manager.
- Review lead.
- Convert lead into client.

**Journey B — Creative production**
- Log in as client.
- Submit brief.
- Log in as agency reviewer.
- Approve brief.
- Trigger AI generation.
- Review creative proposal.
- Create content revision.
- Approve internally.
- Submit for client review.
- Log in as client.
- Approve or request revision.

**Journey C — Task coordination**
- Create task.
- Assign team member.
- Update task status.
- Verify project progress.
- Trigger deadline monitoring.

**Journey D — Reporting**
- Generate project report.
- Verify report metrics.
- Review draft.
- Publish report.
- Verify client access.

### 8.1 Test stability

E2E tests must:
- Use predictable synthetic fixtures.
- Avoid arbitrary sleep delays.
- Wait for meaningful application states.
- Use stable accessible selectors.
- Reset or isolate test data.
- Avoid dependence on live external AI services.

### 8.2 Browser coverage

Minimum:
- Chromium.

Recommended additional coverage:
- WebKit for Safari-related compatibility.
- Firefox for cross-browser confidence.

Do not claim cross-browser compatibility unless those tests have actually run.

---

# Part III — AI Testing

## 9. AI Contract Tests

AI services must validate structured outputs using Pydantic.

Required tests:
- Valid structured response.
- Missing required fields.
- Invalid enum values.
- Excessive output length.
- Empty content.
- Malformed JSON.
- Provider timeout.
- Rate limit.
- Retry exhaustion.
- Generation persistence failure.

### 9.1 Deterministic test provider

Implement a fixture-based provider adapter for automated testing.

Example:

```python
class FixtureLLMProvider:
    async def generate_structured(
        self,
        *,
        system_prompt,
        user_prompt,
        output_schema,
        temperature,
        max_output_tokens,
    ):
        payload = load_fixture_for_schema(output_schema)
        return output_schema.model_validate(payload)
```

The example assumes a fixture loader supplied by the implementation.

Fixture responses must be clearly identified as test data.

They must not be presented as live model output.

## 10. AI Quality Evaluation

Use the synthetic evaluation dataset defined in the AI System Design.

Evaluate:
- Schema validity.
- Brief alignment.
- Brand alignment.
- Factual grounding.
- Creative usefulness.
- Actionability.
- Safety.

Automated tests should verify objective requirements.

Human rubrics should assess subjective quality dimensions.

Do not treat schema validity as proof of content quality.

### 10.1 Evaluation artifacts

Store evaluation artifacts in a documented location.

Recommended:

```text
backend/app/ai/evaluation/
├── datasets/
├── rubrics.py
├── evaluators.py
└── run.py

evaluation/
└── results/
```

Generated results may include:
- Model identifier.
- Prompt version.
- Evaluation date.
- Number of cases.
- Schema validity rate.
- Generation success rate.
- Human scores, where collected.
- Failure categories.

Do not invent evaluation scores.

## 11. AI Security Tests

Test that:
- A client cannot trigger AI generation for another client's brief.
- Unauthorized context is not included in prompts.
- Malicious brief instructions cannot override backend authorization.
- Generated outputs cannot bypass approval.
- Provider credentials never appear in responses.
- Failed generations do not expose raw secrets.

Include prompt-injection test cases using synthetic malicious text.

Backend security must not depend solely on prompt instructions.

---

# Part IV — Automation Testing

## 12. n8n Workflow Tests

Test each workflow independently and as part of an integrated journey.

### Workflow A
- Lead event delivered.
- Agency notification attempted.
- Duplicate event safely handled.
- Failed notification recorded.

### Workflow B
- Approved brief triggers eligible generation.
- Generation status monitored.
- Failed generation stops dependent stages.
- Completed output enters human review.

### Workflow C
- Assignment notification sent.
- Upcoming deadline detected.
- Completed task excluded.
- Duplicate reminder prevented.

### Workflow D
- Scheduled report generation initiated.
- Verified metrics retrieved.
- Draft report created.
- Publication requires human approval.

## 13. Outbox Reliability Tests

Required scenarios:

1. Database transaction succeeds while n8n is unavailable.
2. Outbox event remains pending.
3. Dispatcher retries after n8n recovers.
4. Event is delivered.
5. Duplicate delivery does not duplicate the business operation.

Also test:
- Maximum retry behavior.
- Invalid signatures.
- Event processing failures.
- Concurrent dispatch attempts.

### 13.1 Delivery semantics

The architecture assumes at-least-once delivery.

Tests must not assume exactly-once delivery across distributed services.

## 14. External Integration Testing

Integrations:
- Telegram.
- Gmail.
- Google Drive.
- Google Forms.
- LLM provider.

For automated CI:
- Use mocks, stubs, or fixture adapters.
- Do not require production credentials.

For local integration verification:
- Use explicitly configured test accounts or sandbox resources.
- Confirm actual delivery or upload results.
- Record which integrations were verified.

A successful mock test is not proof that a live external integration works.

---

# Part V — Security Verification

## 15. Authentication and Session Security

Verify:
- Passwords are hashed.
- Sessions expire appropriately.
- Cookies use appropriate security attributes.
- CSRF protections are enforced.
- Logout invalidates the session.
- Authentication errors do not disclose sensitive details.

## 16. Authorization and Client Isolation

This is a critical release gate.

Test with at least two synthetic clients.

Client A must not be able to access Client B's:
- Projects.
- Briefs.
- Files.
- Content.
- Approvals.
- Reports.
- Notifications.

Also verify:
- Client users cannot access admin-only operations.
- Team members cannot perform manager-only actions.
- Internal agency notes are excluded from client responses.
- Client-visible progress contains only approved information.

### 16.1 Direct object reference tests

Attempt to access another client's resource using its known UUID.

The backend must reject unauthorized access.

Do not rely on unpredictable UUIDs as an authorization mechanism.

### 16.2 Delegated authority acceptance tests

Exercise these cases through FastAPI with authenticated sessions and PostgreSQL. Repeat denials by sending the request directly even when the portal hides the action. For each forbidden mutation assert that roles, delegations, approval state, business audit entries and outbox events stay intact. Use fresh fixtures for each decision endpoint.

| Case | Arrange and act | Expected result |
|---|---|---|
| A1 · All agency roles | With two active Admins, Admin invites, grants, suspends, reactivates and revokes each of the three roles on another staff identity. | Each allowed mutation succeeds with one actor/target audit entry and correct before/after state. |
| A2 · Team lifecycle | Manager invites a new Team Member, grants team_member to an eligible existing user, suspends, activates and revokes the team membership. Give the target a separate client membership. | Team access follows the mutation on the next request. Client access and global account status are preserved. |
| A3 · Elevated and self targets | Manager attempts invite/grant/revoke of elevated roles, self-modification, and changing the team membership of someone who also holds an elevated role. Include suspended elevated targets and an invitation target promoted before redemption. | Deny each route. Revalidation prevents an obsolete invitation from conferring access. |
| A4 · Settings and peer authority | Manager changes an operational setting, then tries to patch authentication/security settings or add a security field to the operational request. Team Member attempts peer role management. | Operational change succeeds. Unauthorized changes fail atomically. |
| A5 · Last Admin | Try to disable, delete or demote the sole active Admin. With two active Admins concurrently revoke each other using separate transactions. | Last-Admin guard yields 409 on the sole-admin operation. At most one racing removal commits. A revoked actor loses authority even with an old session. |
| C1 · Client Admin | Active client_admin decides a pending released revision within their client, parameterized over approve and request-revision with feedback. | One binding decision, one audit entry with exact revision and signer, one corresponding event. |
| C2 · Feedback only | Undelegated active member reads and comments on a released revision, then calls each binding endpoint. | Read/comment succeed. Approval remains pending and both binding attempts return 403. |
| C3 · Grant, revoke and regrant | Admin of client A grants a member approval on project A1. Repeat PUT. Member decides on A1, then attempts project A2 of the same client. Revoke, repeat DELETE and try a fresh A1 decision using the existing session. Regrant and decide on a fresh A1 review. | One active grant. A1 actions succeed while delegated. A2 and post-revocation decisions return 403. History retains each effective change and the grant used by each signer. |
| C4 · Tenant and membership | Use client A’s admin and member against client B’s project, membership, content or revision. Deactivate the grantee’s membership or global account after granting. | Cross-client resources are concealed. Inactive principals cannot sign. A second membership in another client conveys no authority over this one. |
| C5 · No onward delegation | A delegated member tries PUT or DELETE for another member and tries to use the grant to modify client roles. Agency-only or service credentials attempt a binding client decision. | Each mutation is denied. The original grant and review survive. |
| C6 · Revision and race | Submit a different item’s revision or a superseded revision. Race approve against request-revision on the same pending request. Repeat the winning request. Separately race revoke against sign-off. | Wrong/unreleased revisions cannot be decided. Exactly one conflicting decision commits. The other and replay return 409. Revocation and sign-off have a serial order. A decision after committed revocation is denied. |
| U1 · Portal actions | Open the same pending review as a client_admin, member and project delegate. Revoke from another session with the review still open. | A member can comment, only eligible signers see binding actions, and only the owning client_admin sees delegation controls. A denied stale action refreshes controls and never displays success. |

CP1 owns A1–A5 and the agency UI permissions as its endpoints become available. CP1-B also covers project grant/revoke, cross-client grant constraints and the delegation UI under the checkpoint authorization. CP2 extends the project UI for operational work. CP4 covers binding decisions, transaction races and the review UI. CP6 reruns the integrated journeys. The CP0 matrix check exercises the documented allow/deny expectations without a running API.

## 17. Secrets and Configuration

Before release:
- Verify `.env` files are ignored.
- Scan the repository for secrets.
- Review n8n exports.
- Review frontend environment variables.
- Review application logs.
- Verify external credentials are not included in test fixtures.

No real credentials may be committed.

## 18. File Security

Verify:
- Upload size limits.
- Allowed file types.
- Filename handling.
- Storage authorization.
- Download authorization.
- Client ownership.
- Safe external URLs.

Files must not become publicly accessible merely because their storage identifiers are known.

## 19. Dependency Security

Use dependency auditing where practical.

Suggested:
- `npm audit` for frontend dependencies.
- `pip-audit` for Python dependencies.
- GitHub Dependabot alerts when available.

Review high-severity findings before release.

Avoid blindly applying breaking dependency upgrades.

---

# Part VI — Local Deployment

## 20. Deployment Target

Primary target:

**Local Docker Compose environment**

Expected services:
- Frontend.
- Backend.
- PostgreSQL.
- n8n.
- Background worker or event dispatcher, if required.

A separate Redis service is not required unless the implementation explicitly adopts a Redis-backed queue.

### 20.1 Resource constraints

The system should be practical to run on a developer laptop.

Avoid requiring:
- Large local foundation models.
- Kubernetes.
- Paid managed databases.
- GPU infrastructure.
- Multiple redundant microservices.

The mechanistic interpretability research environment is separate from the production MVP.

## 21. Docker Compose Requirements

The Compose configuration should:
- Define service dependencies.
- Use health checks where appropriate.
- Persist PostgreSQL data.
- Persist n8n state.
- Configure internal networking.
- Expose only required ports.
- Use environment variables.
- Support clean startup and shutdown.

Example conceptual services:

```yaml
services:
  frontend:
    build: ./frontend
    depends_on:
      - backend

  backend:
    build: ./backend
    depends_on:
      - postgres

  postgres:
    image: postgres:16

  n8n:
    image: n8nio/n8n

  worker:
    build: ./backend
    depends_on:
      - postgres
```

This is an architectural example, not a complete production-ready Compose file.

Codex must implement actual environment variables, health checks, persistent volumes, and service commands.

## 22. Database Initialization

Recommended startup sequence:

1. Start PostgreSQL.
2. Wait for database readiness.
3. Apply Alembic migrations.
4. Start backend services.
5. Start n8n.
6. Start frontend.
7. Run health checks.
8. Optionally seed synthetic demo data.

Avoid automatically resetting or deleting database contents on normal startup.

## 23. Demo Data Seeding

Provide a repeatable seed command.

The seed script should:
- Create synthetic users.
- Create synthetic clients.
- Create projects.
- Create tasks.
- Create briefs.
- Create content items.
- Create example reports.

Seed execution should be idempotent where practical.

Do not seed real personal information.

### 23.1 Demo accounts

Use fictional accounts with documented roles.

Provide credentials through a safe development-only mechanism.

Never deploy publicly accessible demo accounts with predictable passwords.

## 24. Health Checks

Required checks:
- Frontend responds.
- Backend responds.
- Database connection works.
- Worker or dispatcher is operational.
- n8n is reachable.

A health endpoint should not disclose secrets or internal configuration.

Differentiate:
- Liveness.
- Readiness.

A process being alive does not guarantee that its dependencies are ready.

## 25. Backup and Recovery

For local development:
- Use persistent Docker volumes.
- Document PostgreSQL backup and restore.
- Document n8n workflow export and import.
- Document safe reset procedures.

Never use destructive reset commands without clearly warning that local data will be removed.

---

# Part VII — CI/CD

## 26. GitHub Actions

Create a CI workflow that runs on:
- Pull requests.
- Pushes to the main development branch.

Recommended jobs:

**Backend**
- Install dependencies.
- Run formatting checks.
- Run linting.
- Run unit tests.
- Run integration tests with PostgreSQL.

**Frontend**
- Install dependencies.
- Run linting.
- Run TypeScript checks.
- Run component tests.
- Run production build.

**Security**
- Run dependency auditing where practical.
- Check for committed secrets.

**Optional**
- Run selected Playwright tests.

CI must not require real external API credentials.

## 27. CI Failure Policy

A failed required check must block declaring the affected milestone complete.

Do not:
- Suppress failing tests without explanation.
- Remove tests merely to achieve a green build.
- Replace assertions with unconditional passes.
- Mark skipped tests as passed.

Document legitimate exclusions.

## 28. Build Reproducibility

Use:
- Dependency lockfiles.
- Explicit Python dependency versions.
- Documented Node.js version.
- Documented Python version.
- Pinned container image versions where practical.

Avoid floating dependencies for critical production components.

---

# Part VIII — Deployment Verification

## 29. Smoke Test

Provide a smoke test script.

Suggested:

```bash
./scripts/smoke_test.sh
```

The script should verify:
- Frontend availability.
- Backend readiness.
- Database connectivity through backend.
- Authentication endpoint behavior.
- Required service availability.

Smoke tests should fail with a nonzero exit code when critical checks fail.

## 30. End-to-End Demo Verification

Run the complete demonstration journey:

1. Submit public inquiry.
2. Convert lead into client.
3. Create project.
4. Submit creative brief.
5. Approve brief.
6. Generate AI proposals.
7. Select creative direction.
8. Create content draft.
9. Approve internally.
10. Submit for client review.
11. Request revision or approve.
12. Verify task notifications.
13. Generate report.
14. Publish report.
15. Verify client report access.

Record:
- Test date.
- Environment.
- AI provider mode.
- External integration mode.
- Passed steps.
- Failed steps.
- Known limitations.

## 31. Performance Verification

The MVP does not require enterprise-scale load testing.

However, verify:
- Dashboard loading with seeded data.
- API pagination.
- Reasonable query performance.
- No obvious N+1 query issues.
- AI request timeout behavior.
- Worker recovery after restart.

Do not invent latency benchmarks.

Measure and document actual values when available.

## 32. Accessibility Verification

Verify:
- Keyboard navigation.
- Focus indicators.
- Form labels.
- Dialog focus behavior.
- Status announcements.
- Color contrast.
- Responsive layout.
- Reduced-motion handling.

Automated accessibility tools may assist, but manual checks remain necessary.

---

# Part IX — Portfolio Release

## 33. README Requirements

The final README must include:

1. Project overview.
2. Business problem.
3. Solution summary.
4. Architecture diagram.
5. Technology stack.
6. Four integrated workflows.
7. AI architecture.
8. Human-in-the-loop controls.
9. Security architecture.
10. Local installation instructions.
11. Environment configuration.
12. Demo accounts and synthetic data setup.
13. Screenshots.
14. Testing instructions.
15. Evaluation methodology.
16. Known limitations.
17. Research extension.

## 34. Portfolio Evidence

Recommended evidence:
- Client Portal screenshots.
- Admin Dashboard screenshots.
- Creative Studio screenshots.
- Content approval screenshots.
- n8n workflow diagrams.
- Automation monitoring screenshots.
- Architecture diagram.
- Test results.
- AI evaluation results.

Screenshots should represent actual implemented functionality.

Do not present design references or mockups as screenshots of the working product.

## 35. Demo Modes

Support clearly distinguished modes.

### Fixture Mode

Purpose:
- Automated testing.
- Offline demonstrations.
- Predictable results.

Uses:
- Synthetic data.
- Fixture-based AI responses.
- Development notification adapters.

### Live Integration Mode

Purpose:
- Verify actual external service integrations.

Uses:
- Configured LLM provider.
- Configured Telegram or Gmail integration.
- Configured Google Drive integration.

The application must not falsely label fixture responses as live AI-generated results.

## 36. Known Limitations

Document limitations accurately.

Possible examples:
- No automatic social media publishing.
- No advanced visual design editor.
- Limited reporting integrations.
- No enterprise SSO.
- No multi-agency tenancy.
- No real-time collaborative editing.
- Research extension not included in production runtime.

Only include limitations that apply to the actual implemented system.

---

# Part X — Final Release Gates

## 37. Release Gate A — Functional

Required:
- Four workflows implemented.
- Client Portal functional.
- Admin Portal functional.
- End-to-end business journey verified.

## 38. Release Gate B — Security

Required:
- Authentication working.
- Authorization tested.
- Cross-client isolation verified.
- No committed secrets.
- Protected file access.

## 39. Release Gate C — Reliability

Required:
- Workflow idempotency.
- Outbox delivery.
- Error handling.
- Retry behavior.
- AI generation failure recovery.

## 40. Release Gate D — Quality

Required:
- Relevant automated tests pass.
- Frontend builds successfully.
- Backend starts successfully.
- Migrations apply.
- Critical UI interactions work.

## 41. Release Gate E — Documentation

Required:
- README complete.
- Environment configuration documented.
- Setup commands verified.
- Demo instructions available.
- Known limitations recorded.
- Evaluation methodology documented.

A release gate is passed only when supported by actual verification evidence.

---

## 42. Final Instructions for Codex

Implement and verify CREATIVE OS according to the project specifications.

Required behavior:

1. Build incrementally.
2. Follow the implementation roadmap.
3. Run relevant tests after each milestone.
4. Verify actual integrations.
5. Record test results.
6. Fix critical failures before advancing.
7. Keep secrets out of the repository.
8. Preserve client isolation.
9. Preserve human approval.
10. Maintain reproducible local deployment.

Do not claim:
- A test passed unless it was executed.
- An integration works unless it was verified.
- A live AI result was generated when a fixture was used.
- A feature is complete when it contains only placeholders.
- A system is production-ready without supporting evidence.

The final deliverable is a reproducible, working, secure MVP suitable for an AI Automation & System Integration Engineering portfolio.

**CREATIVE OS must demonstrate real integration engineering, measurable AI behavior, and reliable business workflow automation.**
CP4 release verification covers cancel and Escape without writes, exact title and version on confirmation, assigned staff submission and release denial, atomic rollback, concurrent submissions and separate client sign-off.
