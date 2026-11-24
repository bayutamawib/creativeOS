# CREATIVE OS — Project Management & Automation Feature Audit

**Audit date:** 23 November 2026  
**Audit type:** Read-only static repository audit  
**Source of truth:** Current working-tree application code, migrations, workflow definitions, and tests  
**Scope exclusions:** AI evaluation pipeline, `creativeOS-uat-evidence/`, live providers, migrations, Docker/database state, and unrelated functionality

## 1. Executive summary

CREATIVE OS has a real, integrated project-operations foundation. Projects, milestones, internal tasks, project memberships, task assignees, deadlines, statuses, milestone-based progress, brief review, deliverable approval, durable workflow events, assignment notices, deadline scans, and weekly project reports are represented in the database and connected through FastAPI and the Next.js portals. These are not merely mock screens: the repository contains authorization-aware services, migrations, frontend consumers, unit/integration tests, and browser journeys.

The feature set is not yet a complete agency operations product. The largest gap is the dashboard layer. `/admin/dashboard` currently renders agency membership and operational-timezone controls, while `/client/dashboard` mainly provides organization/project selection and approval delegation. There are no dashboard aggregate endpoints, KPI cards, workload summaries, operational charts, project-health panels, or agency analytics route. Project progress bars and automation-history tables exist, but they do not amount to the specified operational dashboard.

Automation is functional only within the repository's local architecture. n8n schedules and webhook workflows are defined and published by the bootstrap script; FastAPI owns idempotent business logic; the worker dispatches durable outbox events; and the development inbox stores notifications. The current notification implementation deliberately refuses delivery outside `APP_ENV=development`, and no Gmail or Telegram provider is implemented in the inspected application path. Therefore communication automation is usable in the local/demo stack but not production-ready for external communication.

Automatic task creation exists in a narrow form: approving a content-plan item creates two deterministic tasks, `Prepare draft` and `Review draft`. Automatic assignment, due-date derivation, capacity-aware distribution, and escalation do not exist. Deadline reminders detect upcoming, due-today, and overdue tasks and revalidate eligibility before delivery, but they do not escalate overdue work to managers or clients.

### Overall classifications

| Requirement | Classification | Short conclusion |
|---|---|---|
| 1. Project management | **IMPLEMENTED** | End-to-end project, milestone, task, membership, assignment, deadline, status, and milestone-progress flows exist. |
| 2. Team monitoring | **PARTIALLY IMPLEMENTED** | Ownership and scoped task lists exist; workload aggregation and team/project health monitoring do not. |
| 3. Client requirements | **IMPLEMENTED** | Client profiles, versioned briefs, approval/revision flows, client authority, and portal views are connected and tested. |
| 4. Dashboard | **PARTIALLY IMPLEMENTED** | Progress bars, report metrics, and automation tables exist; the specified KPI/analytics dashboards and charts do not. |
| 5. Communication automation | **PARTIALLY IMPLEMENTED** | Durable events and local inbox notifications work; Gmail, Telegram, autonomous status messaging, and production delivery do not. |
| 6. Task distribution | **PARTIALLY IMPLEMENTED** | Plan approval creates two idempotent template tasks; assignment is manual and has no scheduling/capacity logic. |
| 7. Deadline reminders | **PARTIALLY IMPLEMENTED** | Daily scheduled reminders and overdue detection exist; escalation and production channels do not. |

No item is classified **UNVERIFIED** at the repository-implementation level because each audited area has enough code to establish its current state. Runtime health in this session remains unverified: no tests, migrations, containers, database calls, or external requests were run. Historical status reports are corroborating context only, not the basis for the classifications.

## 2. Audit method and evidence standard

The audit traced each feature across these layers:

1. Next.js routes and components.
2. FastAPI route registration and handlers.
3. Service-layer authorization and business logic.
4. SQLAlchemy models and Alembic migrations.
5. Worker, outbox, n8n schedules, and notification delivery.
6. Backend and browser tests.

A model, endpoint, or visual component by itself was not treated as an implemented end-to-end feature. **IMPLEMENTED** means the material MVP behavior is connected across the required layers. **PARTIALLY IMPLEMENTED** means a usable subset exists but a named portion of the requirement is absent or local-only. **NOT IMPLEMENTED** means no operative path was found. **UNVERIFIED** is reserved for code whose operation could not be established even statically.

All required specification documents were present. The specification describes dashboard endpoints and analytics that the code does not implement; this audit reports the code state rather than treating planned documentation as delivered functionality.

## 3. Feature coverage matrix

| Capability | Status | Database/backend evidence | Frontend evidence | Tests | End-to-end and usability finding |
|---|---|---|---|---|---|
| Project CRUD and archive | **IMPLEMENTED** | `Project` in `backend/app/models.py`; migration `backend/alembic/versions/0005_projects_projects.py`; handlers `listing`, `create`, `detail`, `update`, `archive` in `backend/app/api/projects.py`; access and audit logic in `backend/app/services/projects.py` | `frontend/app/admin/projects/page.tsx`, `frontend/app/admin/projects/[id]/page.tsx`, `frontend/components/project-list.tsx`, `frontend/components/project-controls.tsx` | `backend/tests/test_projects.py::test_project_crud_scope_and_archive`; `frontend/e2e/projects.spec.ts` | Connected and usable by Admin/Agency Manager; Team Member access is project-scoped; clients receive a filtered projection. |
| Milestones and progress | **IMPLEMENTED** | `Milestone` in `backend/app/project_models.py`; `save_milestone`, `progress`, and `progress_counts` in `backend/app/services/projects.py`; project progress API in `backend/app/api/projects.py` | Admin milestone editing in `frontend/app/admin/projects/[id]/page.tsx`; client-safe milestones in `frontend/app/client/projects/[id]/page.tsx`; cards use `<progress>` in `frontend/components/project-list.tsx` | `backend/tests/test_projects.py::test_milestone_release_and_progress`; `frontend/e2e/projects.spec.ts` | Connected. Progress is the rounded percentage of completed visible milestones, not task completion or weighted effort. Clients see only `client_visible` milestones. |
| Task CRUD, statuses, deadlines | **IMPLEMENTED** | `Task` and status/date constraints in `backend/app/project_models.py`; `create`, `update`, `task_scope` in `backend/app/services/tasks.py`; task handlers in `backend/app/api/projects.py` | Project task cards and forms in `frontend/components/project-controls.tsx`; task schedule in `frontend/app/admin/tasks/page.tsx` | `backend/tests/test_projects.py::test_task_lifecycle_memberships_and_concurrent_events`; `frontend/e2e/projects.spec.ts` | Connected and usable. Managers edit task details and assignments; assigned Team Members can update status. No delete endpoint, dependency graph, recurrence, estimates, or Kanban UI. |
| Project membership and task assignment | **IMPLEMENTED** | `ProjectMember`, `TaskAssignee`; composite membership foreign key; `set_member` in projects service and `assign` in tasks service | Team management and assign/unassign controls on admin project detail | Project lifecycle/concurrency tests and browser project journey | Connected. Assignments require an active agency user who is already a project member. Multiple assignees are supported. |
| Task ownership visibility | **IMPLEMENTED** | `tasks.views` returns assignee IDs/names; `/tasks` accepts `assignee_id`; non-manager `task_scope` restricts results to the current assignee | Task schedule shows assignees; project cards show assignee controls | `test_task_lifecycle_memberships_and_concurrent_events` and browser task journey | Usable for lookup and individual ownership. There is no dedicated “My work” summary beyond the scoped task table. |
| Team workload monitoring | **NOT IMPLEMENTED** | No workload aggregate service or dashboard endpoint was found | No workload cards, utilization view, per-member counts, capacity, or chart | No workload-specific test | Assignment data exists to build this feature, but current UI/API do not aggregate open, overdue, upcoming, or completed work per person. |
| Project health monitoring | **PARTIALLY IMPLEMENTED** | Project status, due date, milestones, task states, reports, and reminders exist separately | Project list/detail shows status, deadline, next milestone, and milestone progress | Project and report tests | Usable per project, but there is no agency-wide at-risk/blocked/overdue project aggregation or health score. |
| Client information | **IMPLEMENTED** | `Client` profile fields in `backend/app/models.py`; client API/service in `backend/app/api/clients.py` and `backend/app/services/clients.py`; lead conversion in intake service | `frontend/app/admin/clients/[id]/page.tsx`, invite and client pages | `backend/tests/test_intake.py`; client isolation tests in project/brief/review suites | Connected. Client records, memberships, invitations, and project association are usable. CRM depth is limited compared with a full account-management system. |
| Brief management | **IMPLEMENTED** | Versioned `Brief`, immutable `Snapshot`, and attachment models in `backend/app/brief_models.py`; routes in `backend/app/api/briefs.py`; logic in `backend/app/services/briefs.py` | Client create/list and shared brief workspace in `frontend/app/client/briefs/*`, `frontend/components/brief-page.tsx`, `brief-workspace.tsx` | `backend/tests/test_briefs.py`; `frontend/e2e/briefs.spec.ts` | Connected from client draft/submission through agency review and approved snapshot. |
| Deliverable approval | **IMPLEMENTED** | Revision-bound reviews, feedback, delegations, and outbox events in `backend/app/review_models.py`, `backend/app/services/reviews.py`, `backend/app/services/review_notifications.py` | Admin/client approval queues and `frontend/components/review-queue.tsx` | `backend/tests/test_reviews.py`; `frontend/e2e/review-cycle.ts`; full journey in `frontend/e2e/intake.spec.ts` | Connected with human gates, exact-revision decisions, client-admin/delegate authority, supersession, and notifications. |
| Dashboard KPI API | **NOT IMPLEMENTED** | No `/dashboard/client`, `/dashboard/agency`, or `/dashboard/team` router/aggregate service exists despite API specification §5.1 | None | None | The application cannot presently serve the specified authorized KPI aggregates. |
| Admin operations dashboard | **NOT IMPLEMENTED** | No backing aggregate endpoint | `frontend/app/admin/dashboard/page.tsx` renders `AgencyMembers` and timezone settings | Foundation tests cover portal access, not operational content | Route exists but is functionally a membership/settings page. It is not an operational dashboard. |
| Client dashboard | **PARTIALLY IMPLEMENTED** | Uses existing client/project and approval-authority APIs | `frontend/app/client/dashboard/page.tsx` provides organization/project selection and delegation controls | Portal/access tests | Usable for access/delegation, but lacks active-project progress, pending approvals, recent notifications, and latest reports in one overview. Project progress lives on separate project routes. |
| KPI cards and charts | **NOT IMPLEMENTED** | Report metrics are calculated but not exposed as dashboard series | No chart library or chart components found; only native progress bars and tables | None | Existing `<progress>` elements are indicators, not operational charts. |
| Automation monitoring | **IMPLEMENTED** | Manager-only endpoints in `backend/app/api/monitoring.py`; correlation/retry logic in `backend/app/services/monitoring.py`; durable records in `backend/app/operations_models.py` | List/detail tables in `frontend/app/admin/automation/page.tsx` and `[id]/page.tsx` | `backend/tests/test_evaluation_monitoring.py`; `frontend/e2e/monitoring.spec.ts` | Connected and usable for recent outbox events, workflow runs, generation jobs, delivery attempts, safe errors, correlation, and constrained retries. It is an activity monitor, not a KPI dashboard. |
| Assignment notifications | **PARTIALLY IMPLEMENTED** | `tasks.assign` emits `task.assigned`; routing and eligibility in `backend/app/services/workflows.py`; n8n definition `automation/n8n/workflows/task-assigned.json` | Agency inbox in `frontend/app/admin/notifications/page.tsx` | `backend/tests/test_projects.py::test_task_workflow_delivery_and_inbox`; browser project journey | End-to-end in the local development inbox. No production email/Telegram delivery. |
| Approval/status notifications | **PARTIALLY IMPLEMENTED** | Content review and report events use `review_notifications.eligible`, `reports.recipients`, and workflow routing | Agency/client notification pages and links to the relevant review/report/task | Review, reminder, and report suites plus browser journeys | Local recipient notifications are connected. General project/task status-change broadcasts and client-facing project updates are not implemented. |
| Automatic task creation | **PARTIALLY IMPLEMENTED** | `backend/app/services/studio.py::decide` creates `Prepare draft` and `Review draft` tasks when a `plan_item` is approved; `source_proposal_id` + `template_step` uniqueness in model/migration prevents duplicates | Triggered through Creative Studio proposal approval; resulting tasks appear in project/task UI | `backend/tests/test_studio.py::test_human_gates_copy_and_idempotent_business_writes` | Connected for one deterministic two-task template. No configurable templates, milestone generation, due dates, or task graph. |
| Automatic assignment/distribution | **NOT IMPLEMENTED** | No assignment policy, capacity query, round-robin, role-skill mapping, or auto-assignment service | Assignment controls are manual | None | `task.assigned` automates notification after assignment; it does not choose an assignee. |
| Scheduled deadline scan | **IMPLEMENTED** | `backend/app/services/reminders.py::scan`; internal route `deadline_scan` in `backend/app/api/workflows.py`; daily cron workflow in `automation/n8n/workflows/deadline-schedule.json`; bootstrap default `0 9 * * *` | Reminders appear in agency inbox | `backend/tests/test_reminders.py::test_deadline_windows` and `test_daily_reservation_and_delivery_rechecks`; browser project journey | Connected in local stack, timezone-aware, recipient-specific, and idempotent per date/window. |
| Overdue detection | **IMPLEMENTED** | `reminders.kind` returns `upcoming`, `due_today`, or `overdue`; open/assigned/current-state checks occur at scan and delivery | Notification message exposes the reason | Reminder tests include timezone, completion, unassignment, and revocation cases | Working within reminder flow. There is no separate overdue register or dashboard KPI. |
| Deadline escalation | **NOT IMPLEMENTED** | No escalation level, repeated-age threshold, manager lookup, or escalation event | No escalation UI | None | Overdue reminders continue to the assignee only; no manager/client escalation path exists. |
| Weekly operational reports | **IMPLEMENTED** | `backend/app/services/report_schedule.py`, `backend/app/services/reports.py`, report models/migration; n8n weekly cron defaults to `0 9 * * 1` | Admin/client report list/detail and review/publish actions | `backend/tests/test_reports.py`; `frontend/e2e/reports.spec.ts` | Connected local workflow with deterministic metrics, draft/review/publication, and client-safe published reports. This does not replace live dashboard analytics. |

## 4. Frontend/backend/database integration findings

### 4.1 Project operations

The API routes are registered under `/api/v1` in `backend/app/main.py`. `backend/app/api/projects.py` exposes project, membership, milestone, task, assignment, completion, and progress operations. The service layer provides the important authorization boundary:

- `backend/app/services/projects.py::scope` returns all active projects to Admin/Agency Manager, only member projects to Team Members, and only owning-organization projects to clients.
- `projects.access` reuses that scope for object access and optionally locks writes.
- `backend/app/services/tasks.py::task_scope` additionally limits non-manager staff to assigned tasks.
- `tasks.assign` requires project membership and creates a durable `task.assigned` outbox event only after the assignment record is persisted.
- Project/milestone/task mutations write activity-log records.

Database constraints reinforce this logic. `Task` includes the owning `client_id`; a composite foreign key binds it to `(project_id, client_id)`. `TaskAssignee` binds an assignee to an existing `(project_id, user_id)` project membership. Date, priority, and status checks are present in `backend/app/project_models.py` and created by `backend/alembic/versions/0005_projects_projects.py`.

The frontend consumes these APIs through server-side helpers and mutation forms. It is functionally complete for list/detail CRUD and assignment, though the interaction design is basic: forms are embedded in details panels, the task view is a table, and there is no Kanban, drag-and-drop, bulk edit, search/filter on tasks, dependencies, comments, time estimates, or recurrence.

### 4.2 Progress semantics

Progress is implemented consistently but narrowly. `projects.progress` counts milestones and completed milestones; client mode adds `Milestone.client_visible = true`. `projects.list_view` computes the same count for cards and selects the next incomplete milestone. Both project portals display the result.

Consequences:

- A project with completed tasks but no completed milestones remains at 0%.
- All milestones have equal weight.
- Blocked or overdue work does not alter the percentage.
- Internal and client percentages may differ by design because the client denominator includes only released milestones.

This is a valid MVP metric but should be labeled “milestone completion,” not generic percent complete, in future analytics.

### 4.3 Team monitoring

The repository stores the necessary primitives—project membership, task assignment, task state, priority, dates, and completion timestamps. The task schedule exposes ownership and deadlines, and managers can query `/tasks?assignee_id=...`. However, no service calculates open tasks per member, overdue tasks per member, upcoming load, blocked work, completion rate, or workload imbalance. No frontend joins those values into a monitoring view.

Accordingly, task ownership is implemented while workload monitoring is not.

### 4.4 Client requirements and approvals

Client records include brand and primary-contact fields. Lead conversion can create the client and initial project transactionally. Client memberships and invitations connect users to organizations. Briefs have explicit draft/submitted/review/approved state, version numbers, snapshots, and files. The approval subsystem binds decisions to an exact content revision and supports internal review, agency release, client approval/revision request, feedback, and per-project delegated authority.

This area is end-to-end and substantially stronger than the dashboard area. The remaining limitations are product breadth, not missing wiring: there is no generalized conversation thread, SLA management, or unified “client requirements” workspace combining briefs, brand context, approvals, and changes.

## 5. Existing dashboard assessment

### 5.1 What exists

- Project cards show status, due date, next milestone, and a milestone progress bar in `frontend/components/project-list.tsx`.
- Project details show milestone progress in both portals.
- The admin task schedule is an operational table with project, assignee, priority, status, and deadline.
- The automation area shows recent events, runs, jobs, attempts, durations, correlations, failures, and retry eligibility.
- Reports store deterministic project-period metrics such as task counts, overdue work, milestone progress, and approval backlog.

### 5.2 What does not exist

- No `/dashboard/agency`, `/dashboard/team`, or `/dashboard/client` backend aggregate endpoint from API specification §5.1.
- No active-client/project/open-task/overdue-task/pending-approval/new-lead/workflow-failure KPI cards.
- No workload breakdown by team member.
- No agency project-health list or blocked/at-risk grouping.
- No creative-pipeline funnel.
- No trend series or chart components.
- No `/admin/analytics` route specified in frontend UX §24.
- No combined client overview of progress, approvals, notifications, and reports.

The `/admin/dashboard` route name is misleading in its current state: it is agency membership and timezone administration. The `/client/dashboard` route is primarily an organization/project and approval-delegation selector. Neither is a placeholder in the sense of being empty, but neither fulfills the dashboard specification.

## 6. Automation and notification architecture

### 6.1 Implemented architecture

The implementation follows a durable event model:

1. Business services commit an `Outbox` event with the domain change.
2. `backend/app/worker.py` claims due events and dispatches a signed, short-lived webhook to n8n using routing in `backend/app/services/workflows.py::ROUTES`.
3. n8n registers the execution through `backend/app/api/workflows.py` and calls scoped generation or delivery endpoints.
4. FastAPI revalidates current authorization/state before delivery.
5. `Notification`, `DeliveryAttempt`, `WorkflowRun`, and `ProcessedEvent` records preserve correlation and idempotency evidence.
6. Manager-only monitoring endpoints expose safe metadata and tightly constrained retry operations.

The workflow files cover lead creation, approved briefs, selected directions, task assignment, content review, deadline reminders, weekly report scheduling, and report notifications. Although exported JSON contains `active: false`, `automation/n8n/bootstrap.sh` imports every definition and runs `n8n publish:workflow` for each workflow ID. It also replaces reminder/report cron expressions from `REMINDER_CRON` and `REPORT_CRON`, defaulting to daily 09:00 and Monday 09:00 respectively.

### 6.2 Notification limitations

`backend/app/services/workflows.py::deliver` explicitly requires `APP_ENV == "development"` and writes to channel `development-inbox`. There is no inspected Gmail or Telegram transport adapter. This is an intentional safe local implementation, not production client communication.

Implemented notification events include:

- new lead;
- task assigned;
- task deadline reminder;
- brief/creative proposals ready;
- content released for client review;
- client approval or revision request;
- report draft and report publication.

Not implemented:

- Gmail delivery;
- Telegram delivery;
- delivery preferences or channel selection;
- client-facing project status-change messages;
- milestone completion notices;
- templated/freeform human-approved client messages;
- read/unread state;
- escalation policies;
- production reconciliation for uncertain third-party sends.

## 7. Missing features and implementation gaps

### Critical MVP gaps

1. **Operational dashboard and aggregate API.** The specified decision-making surface is absent even though the underlying records exist.
2. **Production notification channel.** Local inbox delivery cannot notify users outside the application and is disabled outside development.
3. **Team workload monitoring.** Managers cannot see capacity, overdue ownership, or workload imbalance.
4. **Escalation.** Overdue detection has no manager escalation, acknowledgement, snooze, or resolution state.
5. **Automatic assignment.** Generated tasks are left unassigned and undated.

### Important usability gaps

- No Kanban/board view despite task statuses supporting it.
- No task filtering by status, project, priority, deadline, or assignee in the frontend.
- No project activity timeline despite activity logs being written.
- No bulk task operations.
- No task dependencies, estimates, capacity, or skill/role requirements.
- No weighted or task-derived project progress.
- No agency-wide overdue list or “projects needing attention” view.
- No notification read state or preferences.
- No unified client overview of pending actions.
- Monitoring is limited to recent paged records and does not show aggregate success/failure rates or schedule freshness as KPIs.

## 8. Recommended MVP priorities

| Priority | Recommendation | Why now | Relative complexity |
|---|---|---|---|
| P0 | Add authorized agency/team/client dashboard aggregate endpoints and replace the current route content with operational summaries | Unlocks team monitoring, makes existing data actionable, and satisfies a core MVP acceptance gap | **Medium** |
| P0 | Add one approved production notification adapter behind the existing outbox contract, with preferences and safe failure/reconciliation rules | Current automation cannot reach real recipients | **High** due to credentials, provider uncertainty, privacy, and operations |
| P1 | Add workload aggregation and a manager workload table | Uses existing task/assignment data and directly supports staffing decisions | **Medium** |
| P1 | Add overdue escalation policy and durable escalation events | Completes the deadline-reminder requirement and prevents silent aging | **Medium–High** |
| P1 | Add task filters and an agency-wide overdue/blocked queue | High usability value with modest backend changes | **Low–Medium** |
| P2 | Extend deterministic task templates with configurable offsets, milestone links, project roles, and explicit human confirmation before assignment | Makes automatic task creation operational without unsafe autonomy | **High** |
| P2 | Add a simple status-column board | Improves task operations but should follow filtering and aggregate APIs | **Medium** |
| P2 | Add project activity history | Existing audits make this comparatively inexpensive | **Low–Medium** |
| P3 | Add trends and analytics after trustworthy event definitions and retention are agreed | Avoids charts that look precise but have unstable semantics | **Medium–High** |

Automatic distribution should remain human-confirmed for the MVP. A safe first version can recommend an eligible project member based on project role and current open/overdue count, then require a manager to confirm. Fully autonomous assignment should not precede workload definitions, availability data, and conflict handling.

## 9. Suggested dashboard KPIs and visualizations

### Agency overview

| KPI / visualization | Definition | Recommended display |
|---|---|---|
| Active projects | Non-archived projects in `planning`, `in_progress`, or `in_review` | KPI card with status breakdown |
| Open tasks | Tasks excluding `completed` and `cancelled` | KPI card |
| Overdue tasks | Open tasks with `due_date` before agency-local today | KPI card linking to filtered task table |
| Due in 7 days | Open tasks due today through local date + 7 | KPI card |
| Pending internal reviews | Current pending internal review rows | KPI card |
| Pending client decisions | Current pending client-stage reviews | KPI card |
| Workflow failures | Failed current outbox/run attempts within a defined time window | KPI card plus failure table |
| Project health | Status, milestone progress, overdue task count, blocked task/milestone count, next deadline | Sortable attention table; avoid an opaque score initially |
| Team workload | Open, overdue, due-soon, and in-review tasks per active member | Stacked horizontal bars plus accessible table |
| Task status mix | Counts by task status for active projects | Compact stacked bar |
| Deadline trend | Tasks completed on time vs late by week | Line or grouped bar, only after completion timeliness is formally defined |
| Creative pipeline | Briefs awaiting review → approved → plan items pending → internal review → client review | Funnel or staged count cards |
| Automation health | Successful/failed/running runs, uncertain deliveries, last successful schedule ticks | Status cards and recent-failure table |

### Team Member dashboard

- My open tasks.
- My overdue tasks.
- Due today / due this week.
- Blocked work.
- Tasks awaiting my update.
- Projects and next milestones.

Use a prioritized task table rather than charts for this surface.

### Client dashboard

- Active projects with explicitly labeled milestone progress.
- Next released milestone and target date.
- Deliverables awaiting the user's review.
- Recent client-visible notifications.
- Latest published report.
- Recent released media/deliverables.

No agency workload, internal tasks, internal milestones, or unreleased content should enter client aggregates.

## 10. Risks, dependencies, and estimated implementation complexity

| Risk / dependency | Impact | Mitigation / decision needed | Complexity |
|---|---|---|---|
| Dashboard metric semantics | Incorrect or misleading KPIs, especially “progress” and “active” | Approve exact status sets, timezone boundaries, visibility rules, and progress labels before implementation | **Medium** |
| Authorization and tenant isolation | Aggregate endpoints could leak cross-client or internal agency data | Build aggregates from the same scoped queries used by resource APIs; add negative isolation tests | **High risk**, **Medium implementation** |
| Query performance | Dashboard may issue many counts and joins | Use a bounded aggregate service, indexes on status/due/review fields as justified, and query-count tests | **Medium** |
| Historical trend data | Current-state tables cannot reconstruct every past daily value | Define event-derived metrics or periodic snapshots before trend charts | **High** |
| Multiple assignees | Workload counts can double-count tasks across people | State whether workload means assignments or distinct tasks and display both carefully | **Medium** |
| Progress definition | Milestone-only progress may be mistaken for actual effort/completion | Label it explicitly or approve weighted milestone/task semantics | **Medium** |
| External notification delivery | Provider timeouts and lost acknowledgements can duplicate or obscure sends | Preserve outbox/idempotency model; define provider-specific reconciliation and retention | **High** |
| Escalation fatigue | Daily overdue reminders can spam staff/managers | Define escalation windows, acknowledgement, deduplication, and maximum frequency | **Medium** |
| Auto-assignment fairness | Naive assignment may overload people or assign the wrong skill | Start with recommendations and manager confirmation; add availability/role data first | **High** |
| n8n/runtime dependency | Schedules require the bootstrapped and healthy n8n service plus worker | Add dashboard freshness/last-tick monitoring and operational runbook checks | **Medium** |
| Existing dirty working tree | Future implementation could overwrite ongoing AI/media work | Keep changes narrowly scoped and review diffs against the current working tree | **Process risk** |

## 11. Test coverage assessment

### Existing tests found

- **Project and task API/database:** `backend/tests/test_projects.py` covers project CRUD/scope/archive, milestone visibility/progress, task lifecycle, membership constraints, concurrent assignment events, workflow delivery, inbox access, and cross-client database constraints.
- **Deadline reminders:** `backend/tests/test_reminders.py` covers time windows, daily deduplication, delivery-time rechecks, completion/unassignment suppression, and review notification races.
- **Briefs and files:** `backend/tests/test_briefs.py` covers snapshots, approval, ownership, and file boundaries.
- **Approvals:** `backend/tests/test_reviews.py` covers signer authority, stale/exact revisions, delegation, races, supersession, and queue behavior.
- **Reports:** `backend/tests/test_reports.py` covers deterministic metrics, isolation, report states, frozen evidence, scheduling, and replay.
- **Automation monitoring:** `backend/tests/test_evaluation_monitoring.py` covers failures, safe retry/replay, uncertain delivery, and schedule expiry.
- **Browser journeys:** `frontend/e2e/projects.spec.ts`, `reports.spec.ts`, `review-cycle.ts`, `intake.spec.ts`, and `monitoring.spec.ts` exercise the local end-to-end paths.

### Missing tests corresponding to missing features

- Dashboard aggregate and KPI authorization tests.
- Team workload calculation and multiple-assignee semantics.
- Dashboard query-count/performance tests.
- Production Gmail/Telegram adapter contract tests.
- Overdue escalation policy and deduplication tests.
- Automatic assignee selection and capacity/fairness tests.
- Frontend chart accessibility and responsive dashboard tests.

### Execution status for this audit

No test suite was executed. This was intentional: the user requested a read-only feature audit and prohibited changing Docker/database state. Test files were inspected as evidence of designed and previously exercised behavior, but this document does not claim a fresh passing run. `docs/IMPLEMENTATION_STATUS.md` records historical successful local verification; those records were not independently reproduced in this session.

## 12. Final assessment

CREATIVE OS already has a credible project execution and human-approval core. The strongest verified-by-code areas are resource authorization, project/task persistence, milestone visibility, brief/revision workflows, durable event correlation, local notification delivery, and scheduled reporting/reminders.

The next MVP increment should not rebuild those foundations. It should expose them through authorized aggregate APIs and operational dashboards, add workload and attention views, and complete one production notification channel. Automatic assignment and escalation should follow explicit policy decisions. Until then, project execution is locally usable, but agency monitoring and real-world communication automation remain incomplete.
