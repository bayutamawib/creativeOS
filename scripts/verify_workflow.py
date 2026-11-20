"""Check the exact business event against independent n8n execution metadata."""

import argparse
import subprocess
import time
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
SQL = """
SELECT e.id, r.n8n_execution_id, count(n.id)
FROM outbox_events e
JOIN workflow_runs r ON r.event_id = e.id AND r.status = 'completed'
JOIN processed_events s ON s.event_id = e.id AND s.consumer_name = 'development-inbox'
JOIN notifications n ON n.event_id = e.id AND n.delivery_status = 'delivered'
WHERE e.aggregate_id = :'resource' AND e.event_type = :'kind' AND e.status = 'delivered'
AND (:'revision' = '' OR e.payload->>'revision_id' = :'revision')
GROUP BY e.id, r.n8n_execution_id, e.created_at
ORDER BY e.created_at DESC LIMIT 1;
"""
N8N = """
const { DatabaseSync } = require('node:sqlite');
const db = new DatabaseSync('/home/node/.n8n/database.sqlite', {readOnly:true});
const row = db.prepare('SELECT status FROM execution_entity WHERE id=? AND workflowId=?')
  .get(Number(process.argv[1]), process.argv[2]);
console.log(row?.status ?? 'pending');
"""


def compose(*args, stdin=None):
    return subprocess.run(
        ["docker", "compose", "exec", "-T", *args],
        input=stdin,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    ).stdout.strip()


WORKFLOWS = {
    "report.drafted": "creativeReportW01",
    "report.published": "creativeReportW01",
    "content.client_review_requested": "creativeReviewW01",
    "content.revision_requested": "creativeReviewW01",
    "content.client_approved": "creativeReviewW01",
    "task.deadline_reminder": "creativeDueWf01",
    "lead.created": "creativeLeadWf01",
    "task.assigned": "creativeTaskWf01",
    "brief.approved": "creativeBriefWf01",
    "creative_direction.approved": "creativePlanWf01",
}
STAGES = {
    "brief.approved": ["brief_analysis", "creative_strategy"],
    "creative_direction.approved": ["content_plan"],
}
JOBS = """
SELECT generation_type, provider, g.id
FROM ai_generations g JOIN outbox_events e ON e.id=g.event_id
WHERE e.id=:'event' AND g.status='completed' AND g.snapshot_id=(e.payload->>'snapshot_id')::uuid
AND g.service_identity='n8n:WF-B' ORDER BY generation_type;
"""


def verify_schedule(report):
    row = compose(
        "postgres",
        "psql",
        "-XAt",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        "postgres",
        "-d",
        "creativeos",
        "-v",
        f"report={report}",
        "-f",
        "-",
        stdin="""SELECT r.n8n_execution_id, r.id, g.id
        FROM workflow_runs r JOIN ai_generations g ON g.run_id=r.id
        JOIN scheduled_reports s ON s.run_id=r.id AND s.report_id=g.report_id
        WHERE s.report_id=:'report' AND r.workflow_name='WF-D' AND r.status='completed'
        AND g.service_identity='n8n:WF-D' AND g.status='completed'
        ORDER BY r.created_at DESC LIMIT 1;""",
    )
    if row:
        execution, run, job = row.split("|")
        if (
            compose("n8n", "node", "-e", N8N, execution, "creativeWeeklyW01")
            == "success"
        ):
            print(
                f"PASS weekly report {report}, schedule execution {execution}, run {run}, summary job {job}"
            )
            return
    raise SystemExit("No independently confirmed scheduled summary for this report")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("event_type", choices=[*WORKFLOWS, "report.schedule"])
    parser.add_argument("resource_id", type=UUID)
    parser.add_argument("--revision", type=UUID)
    args = parser.parse_args()
    if args.event_type == "report.schedule":
        verify_schedule(args.resource_id)
        return
    workflow = WORKFLOWS[args.event_type]
    end = time.monotonic() + (
        100 if args.event_type == "task.deadline_reminder" else 35
    )
    while time.monotonic() < end:
        result = compose(
            "postgres",
            "psql",
            "-XAt",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "postgres",
            "-d",
            "creativeos",
            "-v",
            f"resource={args.resource_id}",
            "-v",
            f"kind={args.event_type}",
            "-v",
            f"revision={args.revision or ''}",
            "-f",
            "-",
            stdin=SQL,
        )
        if result:
            event, execution, count = result.split("|")
            if compose("n8n", "node", "-e", N8N, execution, workflow) == "success":
                evidence = ""
                if args.event_type == "task.deadline_reminder":
                    timer = compose(
                        "postgres",
                        "psql",
                        "-XAt",
                        "-U",
                        "postgres",
                        "-d",
                        "creativeos",
                        "-v",
                        f"event={event}",
                        "-f",
                        "-",
                        stdin="SELECT r.n8n_execution_id FROM outbox_events e JOIN workflow_runs r ON r.id=(e.payload->>'scan_run_id')::uuid JOIN outbox_events s ON s.id=r.event_id WHERE e.id=:'event' AND r.status='completed' AND s.event_type='deadline.scan';",
                    )
                    if (
                        not timer
                        or compose("n8n", "node", "-e", N8N, timer, "creativeTimerW01")
                        != "success"
                    ):
                        raise SystemExit("Missing successful schedule execution")
                    evidence = f", originating schedule execution {timer}"
                if args.event_type in STAGES:
                    rows = compose(
                        "postgres",
                        "psql",
                        "-XAt",
                        "-U",
                        "postgres",
                        "-d",
                        "creativeos",
                        "-v",
                        f"event={event}",
                        "-f",
                        "-",
                        stdin=JOBS,
                    ).splitlines()
                    if [r.split("|")[0] for r in rows] != STAGES[args.event_type]:
                        raise SystemExit(
                            "Workflow generations differ from the expected snapshot and stages"
                        )
                    evidence = ", jobs " + ", ".join(rows)
                print(
                    f"PASS {args.event_type} event {event}, n8n execution {execution}, {count} development deliveries{evidence}"
                )
                return
        time.sleep(1)
    raise SystemExit(
        f"Could not verify completed {args.event_type} delivery for {args.resource_id}"
    )


if __name__ == "__main__":
    main()
