# Portfolio demo walkthrough

Start and seed the local stack using the [README](../README.md#run-locally). Use separate browser profiles for the agency and client, because signing in again on the same origin replaces the active session. Use only synthetic names, contacts and attachments. Passwords are in the local, ignored `.local/demo-accounts.json`.

| Identity | Sign-in and role |
|---|---|
| `manager@example.com` | Agency Manager. Runs the walkthrough and manages Team Members |
| `admin@example.com` | Agency Admin. Can manage privileged roles |
| `producer@example.com` | Team Member. Works on assigned projects and tasks |
| `lead@example.com` / `reviewer@example.com` | Northline Studio Client Admin / Client Member. Use these for the project delegation demonstration |
| `publisher@example.com` / `editor@example.com` | Clover Press Client Admin / Client Member. Use these to check that the new client’s project is absent |

## One client and one project

1. In the client profile open [the inquiry form](http://localhost:3100/inquiry). Submit **Aster Press** and **Synthetic Contact** with a fresh address at `example.com`. Add a short suffix to the company and project names when repeating the demo.
2. As the manager, open **Leads**, select the inquiry, choose **qualified** and save the review. Enter **Field Notes Launch** as the initial project name and convert the lead. **Create invitation** produces a single-use link. Open it in the client profile, set a local demo password and sign in. Keep the invitation link and password out of captures.
3. In client **Briefs**, select **Field Notes Launch**, set **Field Notes** as the title and enter an editorial campaign objective. Save and submit. As the manager, open the submitted brief and approve it. The approved version becomes an immutable input snapshot.
4. In agency **Creative Studio**, open that brief. Wait for analysis and strategy, select a direction, then select a plan item. Two project tasks appear. Create the draft deliverable, suggest copy and save it as a new revision.
5. In agency **Approvals**, submit the revision for internal review. Open **Approve & Release to Client**, read the title and revision number, then cancel once to confirm that the client cannot see the draft. Reopen and confirm the same revision. In the client profile open the inbox notification and request a revision. As the manager, revise the headline, submit it again and release the replacement. Sign off in the client portal. The approval binds to the displayed revision.
6. In the agency project, add **Producer** as a member, assign one generated task and mark it completed. A task assignment reaches the producer’s development inbox. In agency **Reports**, select the same project and a reporting period that includes today in the agency timezone. Generate the report, wait for the draft narrative, submit it for review and publish. The owning client can now open or export the report. Expect two total tasks, one completion, one client approval and one revision request when following the steps on a fresh project.
7. In agency **Automation**, select **Workflow runs** and follow a correlated outbox event. Look for the run outcome, n8n execution ID and inbox delivery. In **AI evaluations**, run or open a fixture evaluation and review a synthetic case. Automated contract checks and human assessment appear separately.

To demo delegation, sign in as the Northline Client Admin, choose a project, grant the Northline Client Member approval authority and use another profile to inspect their review access. The grant applies to the selected project. The Client Admin can revoke it.

## Reproduce the browser check

Use a [test copy](LOCAL_OPERATIONS.md#keep-verification-isolated) with distinct Compose volumes and fixture mode. After seeding, run this from `frontend/` with Node 24.

```sh
npm ci
npx playwright install chromium
npm run test:e2e -- intake.spec.ts
```

Set `PLAYWRIGHT_CHANNEL=chrome` to use installed Chrome. For a custom web port set `PLAYWRIGHT_BASE_URL=http://localhost:<port>`. The command prints the created project and report IDs plus event and n8n execution correlations. Set `PORTFOLIO_SCREENSHOT_DIR` to an absolute local directory on the synthetic stack to save the Creative Studio, release confirmation and published report captures.

## Screenshot gallery

These are captures of the local application and the imported n8n workflows using synthetic data. Captures span several synthetic projects on the isolated stack. The one-project walkthrough has separate execution evidence. Repeat runs create new IDs.

| Surface | Screenshot |
|---|---|
| Client Portal | [Client dashboard](screenshots/client-dashboard.png) |
| Admin Portal | [Agency dashboard](screenshots/admin-dashboard.png) |
| Creative Studio | [Approved brief and generation history](screenshots/creative-studio.png) |
| Content approval | [Agency release confirmation](screenshots/release-confirmation.png) and [client decision](screenshots/client-approval.png) |
| Project and tasks | [Project and task management](screenshots/project-tasks.png) |
| Reporting | [Published report in the Client Portal](screenshots/published-report.png) |
| Automation monitoring | [Correlated workflow runs](screenshots/automation-monitoring.png) |
| AI evaluation | [Fixture evaluation results](screenshots/ai-evaluation.png) |
| n8n editor | [Lead intake](screenshots/n8n-lead-workflow.png) and [scheduled reporting](screenshots/n8n-report-workflow.png) |

The application’s workflow records can be verified independently of the editor. See [workflow evidence and troubleshooting](LOCAL_OPERATIONS.md#workflow-evidence-and-troubleshooting).
