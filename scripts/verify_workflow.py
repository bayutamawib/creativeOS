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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("event_type", choices=["lead.created", "task.assigned"])
    parser.add_argument("resource_id", type=UUID)
    args = parser.parse_args()
    workflow = {"lead.created": "creativeLeadWf01", "task.assigned": "creativeTaskWf01"}[
        args.event_type
    ]
    end = time.monotonic() + 35
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
            "-f",
            "-",
            stdin=SQL,
        )
        if result:
            event, execution, count = result.split("|")
            if compose("n8n", "node", "-e", N8N, execution, workflow) == "success":
                print(
                    f"PASS {args.event_type} event {event}, n8n execution {execution}, {count} development deliveries"
                )
                return
        time.sleep(1)
    raise SystemExit(
        f"Could not verify completed {args.event_type} delivery for {args.resource_id}"
    )


if __name__ == "__main__":
    main()
