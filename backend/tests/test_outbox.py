import time
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import engine
from app.intake_inputs import Inquiry
from app.operations_models import Lead, Notification, Outbox, ProcessedEvent, WorkflowRun
from app.security import now
from app.services import intake, workflows


def test_atomic_outbox_and_recovery(workspace):
    data = Inquiry(company_name="Agency", contact_name="Contact", email="contact@example.com")
    with pytest.raises(RuntimeError), Session(engine()) as db, db.begin():
        intake.create(db, data, "client_portal")
        db.flush()
        raise RuntimeError("roll back test transaction")
    with Session(engine()) as db, db.begin():
        for model in (Lead, Outbox):
            assert db.scalar(select(func.count()).select_from(model)) == 0
        intake.create(db, data, "client_portal")
    with Session(engine()) as db, db.begin():
        identifier, first, *_ = workflows.claim(db)
        with Session(engine()) as other, other.begin():
            assert workflows.claim(other) is None
    with Session(engine()) as db, db.begin():
        db.get_one(Outbox, identifier).claim_expires_at = now() - timedelta(seconds=1)
    with Session(engine()) as db, db.begin():
        _, second, *_ = workflows.claim(db)
        assert second != first
        workflows.settle(db, identifier, first, None)
        assert db.get_one(Outbox, identifier).claim_token == second
        workflows.settle(db, identifier, second, None)
        assert db.get_one(Outbox, identifier).status == "pending"
        assert workflows.claim(db) is None


def test_dispatch_lease_is_bounded_after_route_timeout():
    assert workflows.dispatch_timeout("creative-direction-approved") == 45
    assert workflows.dispatch_lease_seconds("creative-direction-approved") == 75
    assert workflows.dispatch_timeout("creative-task-assigned") == 12
    assert workflows.dispatch_lease_seconds("creative-task-assigned") == 42


def test_authenticated_retry_and_delivery(browser):
    guest = browser()
    guest.post(
        "/api/v1/public/inquiries",
        json={"company_name": "Agency", "contact_name": "C", "email": "c@example.com"},
    )
    with Session(engine()) as db, db.begin():
        event_id, claim, _, raw = workflows.claim(db)
    stamp = str(int(time.time()))
    payload = {
        "raw": raw,
        "timestamp": stamp,
        "signature": workflows.signature(stamp + "." + raw),
        "workflow": "WF-A",
        "execution_id": "10",
    }
    path = "/api/v1/internal/workflow-runs"
    assert guest.post(path, json=payload).status_code == 403
    headers = {"X-Creative-Service": workflows.secret(settings().workflow_key)}
    assert (
        guest.post(path, json=payload | {"signature": "0" * 64}, headers=headers).status_code == 403
    )
    assert guest.post(path, json=payload | {"workflow": "WF-D"}, headers=headers).status_code == 409
    first = guest.post(path, json=payload, headers=headers)
    assert first.status_code == 200
    run = first.json()["run_id"]
    assert guest.post(path, json=payload, headers=headers).json() == first.json()
    assert (
        guest.post(
            path + "/" + run + "/outcome", json={"status": "completed"}, headers=headers
        ).status_code
        == 409
    )
    for _ in range(2):
        assert guest.post(path + "/" + run + "/notifications", headers=headers).status_code == 200
    ack = guest.post(
        path + "/" + run + "/outcome", json={"status": "completed"}, headers=headers
    ).json()
    with Session(engine()) as db, db.begin():
        workflows.settle(db, event_id, claim, None)
        assert db.get_one(Outbox, event_id).status == "pending"
        db.get_one(Outbox, event_id).next_attempt_at = now()
    with Session(engine()) as db, db.begin():
        _, second, _, raw = workflows.claim(db)
    payload.update(raw=raw, signature=workflows.signature(stamp + "." + raw))
    second_run = guest.post(path, json=payload | {"execution_id": "11"}, headers=headers).json()[
        "run_id"
    ]
    assert second_run != run
    assert (
        guest.post(path + "/" + second_run + "/notifications", headers=headers).status_code == 200
    )
    ack = guest.post(
        path + "/" + second_run + "/outcome", json={"status": "completed"}, headers=headers
    ).json()
    with Session(engine()) as db, db.begin():
        workflows.settle(db, event_id, second, ack)
        assert db.get_one(Outbox, event_id).status == "delivered"
        assert db.scalar(select(func.count()).select_from(Notification)) == 2
        assert db.scalar(select(func.count()).select_from(ProcessedEvent)) == 1
        assert db.scalar(select(func.count()).select_from(WorkflowRun)) == 2
    assert (
        guest.post(path + "/" + str(uuid4()) + "/notifications", headers=headers).status_code == 404
    )


def test_final_expired_claim_is_observable(workspace):
    data = Inquiry(company_name="Lease", contact_name="Test", email="lease@example.com")
    with Session(engine()) as db, db.begin():
        intake.create(db, data, "manual")
    with Session(engine()) as db, db.begin():
        event_id, _, _, _ = workflows.claim(db)
        event = db.get_one(Outbox, event_id)
        event.attempts = workflows.MAX_ATTEMPTS
        event.claim_expires_at = now() - timedelta(seconds=1)
        db.add(
            WorkflowRun(
                event_id=event_id,
                workflow_name="WF-A",
                workflow_version="1.0",
                n8n_execution_id="42",
                attempt=event.attempts,
            )
        )
    with Session(engine()) as db, db.begin():
        assert workflows.claim(db) is None
        assert db.get_one(Outbox, event_id).status == "failed"
        run = db.scalar(select(WorkflowRun).where(WorkflowRun.event_id == event_id))
        assert run.status == "failed" and run.error_code == "dispatch_lease_expired"
