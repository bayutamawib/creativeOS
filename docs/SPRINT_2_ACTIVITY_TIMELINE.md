# CREATIVE OS — Sprint 2 Activity Timeline

**Completed:** 23 November 2026  
**Scope:** Project activity timeline and Kanban readability  
**Schema migrations:** None

## Architecture findings

Sprint 2 reuses `activity_logs`, the existing project-scoped audit table. Project, membership, milestone, task, brief, content-review, proposal, file, and report services already write real audit rows through `projects.change_log`. No duplicate event store or inferred historical events were introduced.

`GET /api/v1/projects/{project_id}/activity` applies the existing project access query before reading activity. Admins and Agency Managers receive authorized project activity. Team Members receive project/milestone activity plus task events only for tasks currently visible through assignment scope. Clients receive an explicit allowlist of project events, released milestone events, and client-safe content decisions. Internal assignments, tasks, notes, and private milestones are excluded server-side.

## Features implemented

- Reverse-chronological activity with deterministic ID tie-breaking.
- Event type, agency-timezone timestamp, safe actor label, and human-readable description.
- Descriptions for project, team, milestone, task, assignment, and content-review actions.
- Safe fallbacks for system, former, or unavailable actors and targets.
- Twenty-row pagination with newer/older links.
- Shared timeline UI on agency and client project detail pages.
- Empty state and existing route-level loading/error handling.
- Client actor privacy: agency identities appear as `Creative team`.
- Kanban columns now retain a readable 18rem minimum width and scroll horizontally.
- Long task titles wrap only when needed; cards have improved spacing, hierarchy, and focus-independent status selectors.

## Files changed

- `backend/app/api/projects.py`
- `backend/app/services/projects.py`
- `backend/tests/test_projects.py`
- `frontend/app/admin/projects/[id]/page.tsx`
- `frontend/app/client/projects/[id]/page.tsx`
- `frontend/components/project-activity.tsx`
- `frontend/components/task-workspace.tsx`
- `frontend/e2e/projects.spec.ts`
- `docs/SPRINT_2_ACTIVITY_TIMELINE.md`

## Authorization and privacy

- Project access is checked before every activity query.
- Cross-client project IDs return 404 through the existing scoped access service.
- Client visibility uses an explicit action allowlist and requires the milestone target to be currently client-visible.
- Client results never include task, assignment, team-membership, private milestone, internal review, raw audit details, or target IDs.
- Team Member task activity is intersected with the existing `TaskAssignee` scope.
- Raw audit metadata is not returned to the UI.

## Validation results

| Check | Result |
|---|---|
| Ruff on changed backend files | PASS |
| Mypy on 65 backend application modules | PASS |
| Isolated activity integration test | PASS — 1 test |
| Frontend typecheck | PASS |
| Frontend lint | PASS |
| Frontend unit tests | PASS — 3 files, 10 tests |
| Local Next.js production build | PASS |
| Docker frontend production build | PASS |
| Backend, worker, and frontend health | PASS |
| Targeted `e2e/projects.spec.ts` | PASS — 1 test |

The repository-wide backend wrapper also ran unintentionally because it does not forward test selectors. It produced 101 passes, 1 skip, and 30 unrelated failures because the test container resolves historical evidence at `/creativeOS-uat-evidence`, which is not mounted there. No evidence was modified and no external provider was invoked.

## Manual UAT

1. Sign in as a manager and open a project.
2. Confirm the Activity timeline begins with the newest real audit event.
3. Create or update a task and confirm its human-readable event appears after refresh.
4. Use Older/Newer activity and confirm ordering remains stable.
5. Sign in as an assigned Team Member and confirm unrelated task activity is absent.
6. Sign in as the owning client and confirm released milestones appear while tasks, assignments, internal notes, and staff names do not.
7. Open Tasks and confirm six Kanban columns retain readable width and scroll horizontally.
8. Confirm drag/drop and each card's Move task selector still work.

## Known limitations

- Activity descriptions cover known operational actions explicitly and use a safe generic label for newer action types.
- Client visibility reflects the milestone's current release state; withdrawing a milestone removes its history from the client projection.
- Pagination is page-number based rather than cursor based. ID tie-breaking keeps ordering deterministic for equal timestamps.
- Archived projects remain inaccessible through normal project scope, consistent with existing product behavior.
- Native drag-and-drop remains a desktop enhancement; touch and keyboard users use the accessible status selector.
