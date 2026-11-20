import json
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_studio import approved, due, request

from app.ai import evaluation, runner
from app.ai.contracts import GenerationFailure
from app.db import engine
from app.models import Project
from app.operations_models import DeliveryAttempt, Notification, Outbox, WorkflowRun
from app.security import now
from app.services import monitoring, workflows

API = "/api/v1/admin"


def test_evaluation_reproducibility_and_human_rubric(workspace, browser, monkeypatch, tmp_path):
    path = API + "/evaluations"
    admin = browser("manager")
    for name in ("owner", "staff", "foreign"):
        c = browser(name)
        assert c.post(path).status_code == 403 and c.get(path).status_code == 403
    with Session(engine()) as db:
        before = db.scalar(select(func.count()).select_from(Project))
    results = []
    for _ in range(2):
        response = admin.post(path)
        assert response.status_code == 201, response.text
        results.append(admin.get(path + "/" + response.json()["data"]["id"]).json()["data"])
    a, b = results
    assert a["id"] != b["id"] and a["dataset_hash"] == b["dataset_hash"]
    assert a["provider"] == "fixture" and a["model"] == "fixture-v1"
    assert [(r["case_key"], r["checks"], r["output"]) for r in a["cases"]] == [
        (r["case_key"], r["checks"], r["output"]) for r in b["cases"]
    ]
    assert a["aggregates"]["total"] == 56 and a["aggregates"]["passed"] == 56
    assert (
        a["aggregates"]["schema_validity_rate"] == 1 and a["aggregates"]["grounding_passed"] == 50
    )
    assert a["human"]["reviewed"] == 0 and a["human"]["mean_rubric_score"] is None
    assert a["aggregates"]["controls_passed"] == 6
    sample = next(r for r in a["cases"] if r["service"] == "brief_analysis")
    endpoint = path + "/" + a["id"] + "/cases/" + sample["id"] + "/review"
    score = dict(
        brief_alignment=3,
        brand_alignment=2,
        creative_usefulness=3,
        actionability=4,
        safety=True,
        factual_grounding=True,
        disposition="revision_required",
    )
    assert browser("owner").put(endpoint, json=score).status_code == 403
    assert admin.put(endpoint, json=score | {"actionability": 6}).status_code == 422
    assert (
        admin.put(endpoint, json=score | {"disposition": "accepted", "safety": False}).status_code
        == 422
    )
    assert admin.put(endpoint, json=score).status_code == 200
    assert admin.put(endpoint, json=score).status_code == 200
    assert admin.get(path + "/" + a["id"]).json()["data"]["human"] == dict(
        reviewed=1, reviews=1, acceptance_rate=0, revision_rate=1, mean_rubric_score=3
    )
    assert admin.put(endpoint.replace(a["id"], b["id"]), json=score).status_code == 404
    with Session(engine()) as db:
        assert db.scalar(select(func.count()).select_from(Project)) == before
    raw = json.loads(evaluation.DATASET.read_bytes())
    raw["briefs"][0]["objective"] = "Changed scenario"
    replacement = tmp_path / "cases.json"
    replacement.write_text(json.dumps(raw))
    monkeypatch.setattr(evaluation, "DATASET", replacement)
    assert admin.post(path).status_code == 409
    raw["version"] = "creative-eval-test-v2"
    replacement.write_text(json.dumps(raw))
    changed = admin.post(path).json()["data"]
    assert (
        changed["dataset_hash"] != a["dataset_hash"]
        and changed["dataset_version"] != a["dataset_version"]
    )


def test_monitoring_failure_and_safe_replay(workspace, browser):
    manager = browser("manager")
    path, _ = approved(browser("owner"), manager, workspace["north-1"])
    key = request(manager, path).json()["data"]["generation_id"]

    class Timeout:
        def generate(self, *args):
            raise GenerationFailure("provider_unavailable", True)

    for _ in range(3):
        assert runner.execute_one(Timeout())
        due(key)
    jobs = manager.get(API + "/generation-jobs").json()["data"]
    assert (
        len(jobs) == 1
        and jobs[0]["id"] == key
        and jobs[0]["error"] == "provider_unavailable"
        and jobs[0]["attempt"] == 3
        and jobs[0]["retryable"]
    )
    assert not {"input_snapshot", "parameters", "output"} & jobs[0].keys()
    assert browser("owner").post(API + "/generation-jobs/" + key + "/retry").status_code == 403
    assert manager.post(API + "/generation-jobs/" + key + "/retry").status_code == 200
    assert manager.post(API + "/generation-jobs/" + key + "/retry").status_code == 409
    assert runner.execute_one()
    assert manager.get(API + "/generation-jobs").json()["data"][0]["attempt"] == 4
    with Session(engine()) as db, db.begin():
        # The same durable event may acquire a new attempt while preserving its old run.
        event = db.scalars(select(Outbox)).one()
        event.status = "failed"
        event.error_code = "dispatch_unconfirmed"
        event.attempts = workflows.MAX_ATTEMPTS
        r = WorkflowRun(
            event_id=event.id,
            workflow_name="WF-B",
            workflow_version="1.0",
            n8n_execution_id="45",
            attempt=event.attempts,
            status="failed",
            error_code="dispatch_unconfirmed",
            completed_at=now(),
        )
        db.add(r)
        db.flush()
        run_id = r.id
        eid = event.id
    details = manager.get(f"{API}/workflow-runs/{run_id}").json()["data"]
    assert details["event"]["id"] == str(eid) and details["runs"][0]["execution"] == "45"
    assert "payload" not in details["event"]
    for name in ("owner", "staff", "foreign"):
        user = browser(name)
        for suffix in (
            "/outbox",
            "/generation-jobs",
            "/delivery-attempts",
            "/workflow-runs/" + str(run_id),
        ):
            assert user.get(API + suffix).status_code == 403
        assert user.post(f"{API}/workflow-runs/{run_id}/retry").status_code == 403
    assert manager.post(f"{API}/workflow-runs/{run_id}/retry").status_code == 200
    assert manager.post(f"{API}/workflow-runs/{run_id}/retry").status_code == 409
    with Session(engine()) as db, db.begin():
        identifier, token, _, _ = workflows.claim(db)
        assert identifier == eid and db.get_one(Outbox, eid).attempts == 9
        workflows.settle(db, eid, token, None, "dispatch_rejected")
    assert manager.post(f"{API}/outbox/{eid}/retry").status_code == 409


def test_uncertain_delivery_requires_reconciliation(workspace, browser):
    with Session(engine()) as db, db.begin():
        e = Outbox(
            event_type="lead.created",
            aggregate_type="lead",
            aggregate_id=workspace["north"],
            status="failed",
            error_code="dispatch_unconfirmed",
        )
        db.add(e)
        db.flush()
        n = Notification(
            event_id=e.id,
            recipient_id=workspace["owner"],
            channel="email",
            deduplication_key="synthetic",
            message="Synthetic private body",
            delivery_status="sending",
            claim_expires_at=now() - timedelta(seconds=1),
        )
        db.add(n)
        db.flush()
        db.add(DeliveryAttempt(notification_id=n.id, attempt=1, status="sending"))
        db.flush()
        monitoring.reconcile_expired(db)
        monitoring.reconcile_expired(db)
        assert n.delivery_status == "uncertain"
        key = e.id
    manager = browser("manager")
    detail = manager.get(f"{API}/outbox/{key}")
    assert "Synthetic private" not in detail.text
    data = detail.json()["data"]
    assert not data["event"]["retryable"] and len(data["deliveries"]) == 1
    assert (
        data["deliveries"][0]["status"] == "uncertain"
        and data["deliveries"][0]["error"] == "delivery_unconfirmed"
    )
    assert manager.get(API + "/delivery-attempts").json()["data"][0]["event_id"] == str(key)
    assert manager.post(f"{API}/outbox/{key}/retry").status_code == 409

    with Session(engine()) as db, db.begin():
        e = db.get_one(Outbox, key, with_for_update=True)
        e.status = "pending"
        assert workflows.claim(db) is None
        assert e.status == "failed" and e.error_code == "delivery_unconfirmed"


def test_failed_workflow_stage_replays_same_job(workspace, browser):
    import time

    from app.services import creative_workflow

    manager = browser("manager")
    approved(browser("owner"), manager, workspace["north-1"])

    def register(db, execution):
        identifier, token, _, raw = workflows.claim(db)
        timestamp = str(int(time.time()))
        run = workflows.start(
            db, raw, timestamp, workflows.signature(timestamp + "." + raw), execution, "WF-B"
        )
        job = creative_workflow.queue(db, run, "brief_analysis")["generation_id"]
        return identifier, token, run, job

    with Session(engine()) as db, db.begin():
        event, token, first, key = register(db, "43")

    class Timeout:
        def generate(self, *args):
            raise GenerationFailure("provider_unavailable", True)

    for _ in range(3):
        assert runner.execute_one(Timeout())
        due(str(key))
    with Session(engine()) as db, db.begin():
        outcome = creative_workflow.outcome(db, first)
        assert outcome["status"] == "failed"
        workflows.settle(db, event, token, outcome)
    assert manager.post(f"{API}/workflow-runs/{first}/retry").status_code == 200
    with Session(engine()) as db, db.begin():
        eid, token, second, retried = register(db, "44")
        assert eid == event and second != first and retried == key
    assert runner.execute_one()
    with Session(engine()) as db, db.begin():
        assert creative_workflow.poll(db, second, key)["status"] == "completed"
        creative_workflow.queue(db, second, "creative_strategy")
    assert runner.execute_one()
    with Session(engine()) as db, db.begin():
        outcome = creative_workflow.outcome(db, second)
        workflows.settle(db, event, token, outcome)
    data = manager.get(f"{API}/outbox/{event}").json()["data"]
    assert [r["status"] for r in data["runs"]] == ["completed", "failed"]
    assert len(data["receipts"]) == 1 and len(data["deliveries"]) == 2
    assert len(data["jobs"]) == 2


def test_interrupted_schedule_expires_while_its_summary_recovers(workspace):
    from app.services import report_schedule

    with Session(engine()) as db, db.begin():
        db.get_one(Project, workspace["north-1"]).status = "in_progress"
        run_id = report_schedule.register(db, "877", now())
        assert report_schedule.status(db, run_id, enqueue=True)["status"] == "running"
        run = db.get_one(WorkflowRun, run_id)
        run.last_callback_at = now() - timedelta(minutes=11)
        monitoring.reconcile_expired(db)
        assert run.status == "failed" and run.error_code == "schedule_callback_expired"
    assert runner.execute_one()
    with Session(engine()) as db, db.begin():
        new = report_schedule.register(db, "878", now())
        assert (
            new != run_id and report_schedule.status(db, new, enqueue=True)["status"] == "completed"
        )
