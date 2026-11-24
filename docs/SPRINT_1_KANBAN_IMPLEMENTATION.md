# CREATIVE OS — Sprint 1 Kanban Implementation

**Implementation date:** 23 November 2026  
**Scope:** Agency task board, table parity, task filters, safe status transitions  
**Schema migrations:** None

## 1. Features implemented

### Kanban board

- Added a responsive board at `/admin/tasks` using all existing task statuses: `todo`, `in_progress`, `in_review`, `completed`, `blocked`, and `cancelled`.
- Task cards show title, project, priority, assignees, due date, and an agency-timezone-aware overdue indicator.
- Added native drag-and-drop status movement for pointer users.
- Added a labeled status selector to every card and table row as the keyboard, screen-reader, and touch alternative.
- Added per-column counts, empty columns, an overall no-results state, mutation progress, and an `aria-live` result message.
- Task titles link to the exact task card on the existing authorized project detail page.
- Added a responsive loading skeleton. The existing application error boundary handles task-page read failures, while failed or denied mutations render their backend error in the live status region.
- Closed-task rules remain unchanged: managers can reopen a completed/cancelled task to `todo`; Team Members cannot move a closed task. Only managers can cancel work.

### Task filtering

Added combinable server-side filters for:

- project;
- status;
- priority;
- assignee;
- due-date start;
- due-date end;
- overdue or not overdue.

The filter form is shared by board and table views. Filter values survive view changes and pagination. “Reset filters” clears every filter while retaining the selected view. Invalid date ranges return HTTP 422.

### Board/table views

- Preserved the task table and added a visible Board View / Table View switch.
- Both views render the same authorized, filtered API result.
- Both views expose the same task detail link and accessible status control.
- Pagination uses 100 tasks per page in both views.

### Concurrent status updates

Task responses now include `updated_at`. Board/table mutations send it as `expected_updated_at`. The backend compares that precondition after acquiring the existing project write lock. A stale concurrent edit returns HTTP 409 instead of silently overwriting the newer status.

## 2. Files changed

| File | Change |
|---|---|
| `backend/app/api/projects.py` | Added task query filters, date-range validation, agency-local overdue filtering, and overdue response calculation. |
| `backend/app/project_inputs.py` | Added optional `expected_updated_at` to task updates. |
| `backend/app/services/tasks.py` | Added `updated_at`/`is_overdue` projections and stale-write validation while retaining existing locks, role checks, transition rules, audit logs, and assignment events. |
| `backend/tests/test_projects.py` | Added combined-filter, overdue, role-scope, cross-client denial, invalid-range, and concurrent stale-update coverage. |
| `frontend/app/admin/tasks/page.tsx` | Replaced the table-only task page with filters, view switching, consistent pagination, and authorized filter options. |
| `frontend/app/admin/tasks/loading.tsx` | Added an accessible responsive loading state. |
| `frontend/components/task-workspace.tsx` | Added the board, preserved table rendering, drag/drop, accessible status controls, overdue treatment, empty state, and mutation feedback. |
| `frontend/components/project-controls.tsx` | Added stable task-card anchors for task-detail links. |
| `frontend/lib/projects.ts` | Extended the task contract with `updated_at` and `is_overdue`. |
| `frontend/lib/task-statuses.ts` | Added the boundary-neutral, typed status values, labels, guard, and role-aware transition options shared by server and client components. |
| `frontend/lib/task-filters.ts` | Centralized task query serialization so board, table, and pagination links preserve the same filters. |
| `frontend/tests/task-statuses.test.ts` | Added regression coverage for the runtime status contract, backend values, transition choices, and filter-preserving links. |
| `frontend/e2e/projects.spec.ts` | Extended the project journey with combined filters, overdue UI, board/table parity, accessible status movement, column placement, filter reset, and exact-project cleanup. |
| `docs/SPRINT_1_KANBAN_IMPLEMENTATION.md` | This implementation record and UAT checklist. |

No AI pipeline, prompt, evaluation evidence, migration, n8n workflow, external integration, or historical approval file was changed for this sprint.

## 3. Architecture and API changes

### Extended endpoint

`GET /api/v1/tasks` retains its existing pagination and `assignee_id` behavior and now accepts:

| Query parameter | Type | Behavior |
|---|---|---|
| `project_id` | UUID | Restricts results to an accessible project. |
| `status` | Existing `TaskStatus` literal | Restricts results to one existing status. |
| `priority` | Existing `Priority` literal | Restricts results to one existing priority. |
| `assignee_id` | UUID | Restricts results to tasks assigned to the user, intersected with actor scope. |
| `due_from` | Date | Inclusive lower due-date bound. |
| `due_to` | Date | Inclusive upper due-date bound. |
| `overdue` | Boolean | `true` returns open work due before agency-local today; `false` excludes that work. |

All filters are combined with SQL `AND`. Invalid enum, UUID, date, or Boolean values use FastAPI validation. A `due_from` later than `due_to` returns 422.

Task projections add:

- `updated_at`: optimistic-concurrency token;
- `is_overdue`: deterministic server result based on the configured agency timezone and excluding completed/cancelled tasks.

### Extended mutation contract

`PATCH /api/v1/tasks/{task_id}` accepts optional `expected_updated_at`. Existing callers remain compatible. When supplied, it must match the task after the existing project-level write lock and refresh. A mismatch returns 409.

No new endpoint, table, index, migration, package, or client-side state dependency was introduced.

### Next.js runtime boundary correction

The first implementation exported `TASK_STATUSES` from `frontend/components/task-workspace.tsx`, a `"use client"` module, and imported it into the server-rendered task page. Next.js represents exports crossing that React Server Component boundary as client references; the value therefore type-checked and built but was not a normal array during server rendering. Calling `.map()` caused the production-only `TASK_STATUSES.map is not a function` exception.

Status data now lives in `frontend/lib/task-statuses.ts`, which has no client directive or component dependency. Server and client components import that single runtime contract directly. There is no circular dependency and no duplicate status list.

## 4. Authorization and tenant-isolation safeguards

- All filters are applied after `tasks.task_scope`; they can narrow authorized results but cannot broaden them.
- Admins and Agency Managers retain agency-wide active-project scope.
- Team Members retain project-membership plus task-assignment scope. Filtering by another assignee cannot expose that assignee's unrelated work.
- Client users remain denied access to internal task APIs.
- A supplied project UUID is intersected with the actor's scoped task query; it is not trusted as authorization.
- Status mutations continue through `tasks.get(..., write=True)`, which rechecks task scope and serializes writes on the owning project.
- Existing transition restrictions are unchanged: assigned staff can change only status, only managers can cancel, and closed work must be manager-reopened to `todo`.
- Existing `task.updated` activity logging remains in the same transaction.
- Assignment records and `task.assigned` outbox behavior were not changed.
- Existing composite database constraints continue to bind tasks to the correct project/client and assignees to project membership.

## 5. Test results

### Passed

| Command | Result |
|---|---|
| `backend/.venv/bin/ruff check backend/app/api/projects.py backend/app/project_inputs.py backend/app/services/tasks.py backend/tests/test_projects.py` | Passed. |
| `backend/.venv/bin/mypy backend/app` | Passed: no issues in 65 application modules. |
| `npm run typecheck` in `frontend/` | Passed. |
| `npm run lint` in `frontend/` | Passed. |
| `npm test` in `frontend/` | Passed: 3 files, 10 tests. |
| `docker compose build frontend` | Passed: production image compiled successfully. |
| `docker compose up -d --no-deps frontend` | Passed: rebuilt container became healthy. |
| `npm run test:e2e -- e2e/projects.spec.ts` in `frontend/` | Passed: 1 test in 35.5 seconds. |
| `git diff --check` for Sprint 1 files | Passed. |

### Backend integration coverage

`backend/tests/test_projects.py::test_task_filters_overdue_scope_and_stale_status_update` covers:

- combined project + status + priority + assignee + overdue filtering;
- agency-timezone overdue output;
- non-overdue filtering;
- Team Member assignment scope;
- client denial;
- invalid due-date ranges;
- two concurrent authorized status changes using one version, with one expected 200 and one expected 409.

The existing project tests continue to cover task visibility by role, unauthorized detail/status changes, assignment membership, cross-client database constraints, allowed status lifecycle, activity/outbox behavior, and concurrent assignment.

The dedicated test `tests/test_projects.py::test_task_filters_overdue_scope_and_stale_status_update` passed before this continuation. No backend source was changed while completing the runtime correction.

The executed Playwright project journey covers:

- combined UI filters;
- overdue presentation;
- board/table data consistency;
- the accessible status-change alternative;
- placement in the destination board column;
- filter reset;
- the existing responsive client-safe project journey.

The local stack was verified as `APP_ENV=development` with fixture AI and local file providers before E2E writes. The test creates UUID-suffixed records and archives only the exact project ID it created, including from `finally` after failures. Archiving preserves audit history and is intentionally not described as deletion.

The current backend image required the repository's existing additive `0016_quality_findings` migration before readiness. The migration was applied to the local development database; no migration file or historical record was edited. The backend and outbox worker were then healthy. Frontend logs contained no `TASK_STATUSES` or task-page runtime exception after validation.

## 6. Known limitations

- Each task page contains at most 100 records. Board and table remain consistent within the selected page, not across every page at once.
- Project filter options load the first 100 accessible projects. The backend accepts any authorized project filter, but organizations with more than 100 active projects need searchable/paginated filter options.
- Native HTML drag-and-drop is primarily a desktop pointer interaction. Mobile and keyboard users use the fully supported status selector.
- Task detail access opens the anchored task card on the project detail page; there is no new standalone task-detail route.
- Project, status, priority, and assignee filters select one value per category. Categories combine, but multi-select within one category is not included.
- Filters are URL-based but are not saved as named views.
- Status changes wait for the API response and server refresh; the UI does not use speculative optimistic movement.
- Closed-task and cancellation transition rules deliberately match the pre-sprint backend rather than introducing a new workflow state machine.
- E2E cleanup archives its exact test-owned project rather than deleting rows. Historical test records from runs predating this cleanup remain in the development database and require ownership verification before any manual removal.

## 7. Manual UAT checklist

### Manager

- [ ] Sign in as Admin or Agency Manager and open **Tasks**.
- [ ] Confirm Board View contains To do, In progress, In review, Completed, Blocked, and Cancelled columns.
- [ ] Confirm each card shows project, priority, assignees, and deadline.
- [ ] Confirm overdue open work has a red border and “Overdue” label.
- [ ] Apply project, status, priority, assignee, due-date, and overdue filters together.
- [ ] Confirm only matching tasks appear.
- [ ] Switch to Table View and confirm the same tasks remain visible.
- [ ] Reset filters and confirm all controls clear without changing the selected view.
- [ ] Drag an open task to another allowed column and confirm it remains there after reload.
- [ ] Change another task with the Move task selector and confirm the live success message.
- [ ] Open a task title and confirm the browser lands on its exact project task card.
- [ ] Cancel an open task and confirm only a manager sees that option.
- [ ] Reopen a completed/cancelled task and confirm the only permitted destination is To do.

### Team Member

- [ ] Sign in as a Team Member and confirm only assigned tasks from member projects appear.
- [ ] Confirm filtering by project/assignee cannot reveal other users' tasks.
- [ ] Move an assigned open task by selector and drag/drop.
- [ ] Confirm Cancelled is not an available destination.
- [ ] Confirm a closed task cannot be moved.

### Accessibility and responsive behavior

- [ ] Complete filtering, view switching, task navigation, and status movement using only a keyboard.
- [ ] Confirm every status selector has an accessible name containing the task title.
- [ ] Confirm screen-reader landmarks identify Task results and each named board column.
- [ ] Confirm status errors/successes are announced from the live region.
- [ ] At mobile width, confirm filters stack, cards remain readable, board columns stack, and the table scrolls horizontally.
- [ ] Confirm reduced-motion preference disables loading animation.

### Security and concurrency

- [ ] Attempt `/api/v1/tasks` as a client user and confirm denial.
- [ ] Attempt to patch an unassigned task as a Team Member and confirm no resource is exposed.
- [ ] Submit two changes using the same `expected_updated_at`; confirm the stale request returns 409 and the successful update remains stored.

## 8. Remaining follow-up work

1. Add searchable server-backed project and assignee selectors for agencies exceeding 100 records.
2. Consider a dedicated authorized task-detail route if task comments, files, or history are added.
3. Consider saved filters and multi-select status/priority controls after observing real workflow needs.
4. Add explicit touch-oriented drag interactions only if usability testing shows the selector is insufficient.
