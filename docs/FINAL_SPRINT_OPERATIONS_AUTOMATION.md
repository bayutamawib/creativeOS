# CREATIVE OS — Final Sprint Operations & Automation

**Completed:** 23 November 2026  
**Scope:** Authorized operations dashboards and validated workflow automation  
**Migrations/dependencies:** None

## Features implemented

### Agency operations dashboard

The existing `/admin/dashboard` now includes an authorized operational overview before the existing member-management controls:

- active project count;
- open task count;
- overdue task count using the configured agency date;
- completed-task rate excluding cancelled work;
- open and overdue workload grouped by assignee, including unassigned work;
- milestone-based progress for the ten most recently updated active projects.

Admins and Agency Managers see agency-wide active data. Team Members see only member projects and their assigned tasks through the pre-existing scope queries.

### Client dashboard

The existing `/client/dashboard` now shows only data belonging to the selected active client membership:

- client-visible project progress and next milestone;
- released milestone names, states, and dates;
- creative brief title and current workflow status;
- pending client approvals linked to the existing review queue.

The response contains no tasks, assignees, workload, internal milestone, internal feedback, or audit metadata.

## Architecture and reused infrastructure

Two read-only endpoints were added:

- `GET /api/v1/dashboard/agency`
- `GET /api/v1/dashboard/client?client_id={uuid}`

The agency endpoint reuses `projects.scope`, `tasks.task_scope`, task assignments, project memberships, milestones, and the agency-local date calculation. The client endpoint first validates an active `ClientMembership`, then reuses client project scope and the existing client-safe milestone, brief, and exact-revision approval models.

No dashboard table, cache, scheduled aggregation, charting library, migration, or background job was introduced.

Existing automation was retained unchanged:

- Brief submission and manager approval use the versioned brief state machine and project audit log.
- Task assignment commits one `task.assigned` outbox event for the immutable assignment ID.
- The worker claims committed outbox rows with leases and safe retry state.
- n8n invokes the existing authenticated/scoped callbacks.
- Deadline scans derive the date in the agency timezone.
- Reminder IDs are deterministic per task, recipient, channel, local date, and reason, preventing duplicates.
- Delivery rechecks active project, task, assignment, user, date window, and task state.
- Client review notifications recheck active membership, exact current revision, and pending decision.
- Tests use fixture AI, local storage, and the development inbox; no real external message or AI call is made.

## Requirement mapping

| Portfolio requirement | Delivered capability |
|---|---|
| Project management | Existing project, milestone, task, assignment, deadline, Kanban, filter, and activity features. |
| Operational dashboard | Active projects, open/overdue tasks, completion rate, and active-project progress. |
| Team monitoring | Authorized workload grouped by assignee with overdue counts. |
| Client requirements | Versioned brief states and client dashboard requirement tracking. |
| Client progress | Client-visible milestone progress and next milestone only. |
| Approval monitoring | Pending exact-revision client decisions linked to the review queue. |
| Task distribution | Existing manager assignment, membership validation, durable outbox, and recipient recheck. |
| Deadline reminders | Existing timezone-aware scan, deterministic reservation, idempotent delivery, and inbox visibility. |
| Client communication | Existing client-review, decision, report, and local development notification path. |

## Files changed

- `backend/app/api/dashboard.py`
- `backend/app/services/dashboard.py`
- `backend/app/main.py`
- `backend/tests/test_dashboard.py`
- `backend/tests/test_reminders.py`
- `frontend/app/admin/dashboard/page.tsx`
- `frontend/app/client/dashboard/page.tsx`
- `frontend/components/operations-dashboard.tsx`
- `frontend/e2e/projects.spec.ts`
- `docs/FINAL_SPRINT_OPERATIONS_AUTOMATION.md`

Sprint 2 files are documented separately in `docs/SPRINT_2_ACTIVITY_TIMELINE.md`.

## Tests and results

| Check | Result |
|---|---|
| Ruff for changed backend files | PASS |
| Mypy for 67 backend application modules | PASS |
| Dashboard + assignment + reminder + client-notification integration selection | PASS — 4 tests |
| Frontend typecheck | PASS |
| Frontend lint | PASS |
| Frontend unit tests | PASS — 3 files, 10 tests |
| Local Next.js production build | PASS |
| Docker frontend production build | PASS |
| Backend, worker, and frontend container health | PASS |
| Targeted `e2e/projects.spec.ts` | PASS — 1 test |

The isolated backend run creates a uniquely named PostgreSQL database and drops that exact database on exit. The browser journey creates UUID-suffixed records and archives only its exact project in normal completion and `finally` cleanup.

## Reproducible demo

1. Start the Compose stack with `APP_ENV=development`, `AI_PROVIDER=fixture`, `AI_MODEL=fixture-v1`, and `FILE_PROVIDER=local`.
2. Sign in as a manager and open **Dashboard** to view agency KPIs, workload, and project progress.
3. Create a project for a demo client.
4. Sign in as that client's admin, create and submit a brief, and confirm its submitted status on the client dashboard.
5. As manager, approve the brief, add a team member, create an overdue task, and assign it.
6. Open **Tasks**, filter to the project, and move the task from Board or Table view.
7. Return to **Dashboard** and observe open/overdue workload and project progress.
8. Run the existing local deadline scan/n8n workflow and confirm the assigned member receives one development-inbox reminder.
9. Complete the task as the assigned member.
10. As the client, confirm the dashboard shows only shared project progress, milestones, brief state, and pending approvals—not internal tasks or assignments.

Automated equivalent:

```bash
npm --prefix frontend run test:e2e -- e2e/projects.spec.ts
```

Run it only after confirming fixture/local providers and a safe development database.

## Known limitations

- Dashboard values are live queries rather than historical trends; there are no time-series charts.
- Active-project progress is milestone based and displays the ten most recently updated active projects.
- Task completion rate is current-state based, not a period metric.
- Workload counts assignments, so a task with multiple assignees contributes to each person's workload.
- The client dashboard shows all briefs in its authorized active projects; named saved filters are not included.
- Notifications use the durable local development inbox in the validated environment. Production Gmail/Telegram credential setup remains an operational deployment concern.
- Archival preserves test history. Older test records created before exact-ID cleanup are not deleted without ownership verification.
