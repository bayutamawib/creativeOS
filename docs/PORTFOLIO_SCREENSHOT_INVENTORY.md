# Portfolio Screenshot Inventory

Audit date: 2026-11-24. All files below were opened and visually inspected at their full captured page size. The current captures use synthetic local demo data. Historical evidence remains under `creativeOS-uat-evidence/` and is not replaced by these files.

| Module | Current image | Status | Review note |
|---|---|---|---|
| Agency Dashboard | `agency-dashboard.png` | PASS | Valid agency dashboard; visible addresses are synthetic `example.com` demo records. |
| Projects | `projects.png` | PASS | Agency project cards and progress are visible. |
| Project Detail | `project-detail.png` | PASS | Project team, timeline, tasks, and asset sections are visible. |
| Kanban / Task Assignment | `kanban-task-assignment.png` | PASS | Task board, filters, assignments, deadlines, and status columns are visible. |
| Project Timeline | `project-timeline.png` | REVIEW | Valid page, but duplicate content of `project-detail.png`; retain as evidence, omit from gallery. |
| Brief Management | `brief-management.png` | PASS | Brief list, approved synthetic brief, project files, and brief form are visible. |
| Brief Analysis | `creative-studio-brief-analysis.png` | PASS | Creative Studio Brief Analysis stage shows persisted generation metadata and output controls. |
| Creative Strategy | `creative-studio-creative-strategy.png` | PASS | Strategy stage shows two directions and approval state. |
| Content Plan | `creative-studio-content-plan.png` | PASS | Content Plan stage shows proposals, channels, and selection controls. |
| Copywriting | `creative-studio-copywriting.png` | PASS | Copywriting stage shows live-compatible metadata, revision history, and draft copy. |
| Internal Review | `internal-approvals.png` | PASS | Agency review queue and review controls are visible. |
| Client Dashboard | `client-dashboard.png` | PASS | Client workspace, project progress, briefs, and pending approvals are visible. |
| Client Projects | `client-projects.png` | PASS | Client project cards and synthetic assets are visible. |
| Client Project Detail | `client-project-detail.png` | PASS | Valid client project page with timeline, asset controls, and intentional empty media states. |
| Client Approval | `client-approvals.png` | PASS | Released content details, revision state, and client feedback controls are visible. |
| Agency Reports | `agency-reports.png` | PASS | Project reporting metrics, report generation form, and report history are visible. |
| Client Reports | `client-reports.png` | REVIEW | Valid client page, but currently shows an empty published-reports state. |
| Agency Notifications | `agency-notifications.png` | PASS | Development inbox with workflow notifications is visible. |
| Client Notifications | `client-notifications.png` | PASS | Client inbox with a review notification is visible. |
| Automation Monitoring | `automation-monitoring.png` | PASS | Outbox activity, workflow states, attempts, durations, and correlations are visible. |
| AI Evaluation | `ai-evaluations.png` | PASS | Fixture evaluation history and check counts are visible. |
| Leads | `leads.png` | PASS | Lead pipeline, contacts, statuses, and filtering controls are visible. |
| Clients | `clients.png` | PASS | Valid client directory; visible addresses are synthetic `example.com` demo records. |
| Attachment Management | `attachment-management.png` | PASS | Client-safe project file listing with synthetic file metadata is visible. |

## Publishable set

The gallery includes only the 22 screenshots marked PASS. Two REVIEW images remain preserved in `docs/screenshots/current/` and are excluded from the gallery because one duplicates another capture and one is an empty reports state. No login redirects, application errors, loading skeletons, or broken layouts were observed.
