from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_reviews import draft as draft

from app.config import settings
from app.db import engine
from app.operations_models import Notification, Outbox, WorkflowRun
from app.security import now
from app.services import reminders, workflows


def test_deadline_windows(browser, workspace, monkeypatch):
    utc = datetime(2026, 11, 20, 17, tzinfo=UTC)
    before = reminders.day(utc - timedelta(microseconds=1))
    after = reminders.day(utc)
    assert (before.day, after.day) == (20, 21)
    assert [reminders.kind(after, day) for day in (before, after, after + timedelta(days=1))] == [
        "upcoming",
        "due_today",
        "overdue",
    ]
    assert (
        reminders.kind(None, before) is None
        and reminders.kind(after + timedelta(days=1), before) is None
    )
    monkeypatch.setenv("AGENCY_TIMEZONE", "America/New_York")
    settings.cache_clear()
    assert reminders.day(utc) == before


def test_daily_reservation_and_delivery_rechecks(browser, workspace):
    manager = browser("manager")
    pid = workspace["north-1"]
    p = f"/api/v1/projects/{pid}"
    who = str(workspace["staff"])
    manager.post(p + "/members", json={"user_id": who})
    today = reminders.day(now())
    tasks = []
    for name in ["active", "completed", "unassigned", "closed_before_scan"]:
        tid = manager.post(p + "/tasks", json={"title": name, "due_date": str(today)}).json()[
            "data"
        ]["id"]
        path = "/api/v1/tasks/" + tid
        manager.post(path + "/assign", json={"user_id": who})
        if name == "closed_before_scan":
            manager.post(path + "/complete")
        tasks.append(path)
    service = browser()
    endpoint = "/api/v1/internal/workflow-runs/deadline-scan"
    data = {"execution_id": "123"}
    assert service.post(endpoint, json=data).status_code == 403
    headers = {"X-Creative-Service": workflows.secret(settings().workflow_key)}
    gate = Barrier(2)
    services = [service, browser()]

    def tick(i):
        gate.wait()
        return services[i].post(endpoint, json=data, headers=headers).json()

    with ThreadPoolExecutor(2) as pool:
        a, b = pool.map(tick, range(2))
    assert a == b and a["status"] == "completed"
    assert service.post(endpoint, json={"execution_id": "124"}, headers=headers).status_code == 200
    manager.post(tasks[1] + "/complete")
    manager.delete(tasks[2] + "/assignees/" + who)
    with Session(engine()) as db, db.begin():
        events = list(
            db.scalars(select(Outbox).where(Outbox.event_type == "task.deadline_reminder"))
        )
        assert len(events) == 3
        for e in events:
            e.attempts = 1
            run = WorkflowRun(
                event_id=e.id,
                workflow_name="WF-C",
                workflow_version="1.0",
                n8n_execution_id="130",
                attempt=1,
            )
            db.add(run)
            db.flush()
            workflows.deliver(db, run.id)
            workflows.deliver(db, run.id)
        assert db.scalar(select(func.count()).select_from(Notification)) == 1
    staff = browser("staff")
    assert [n["resource_id"] for n in staff.get("/api/v1/notifications").json()["data"]] == [
        tasks[0].split("/")[-1]
    ]
    manager.delete(p + "/members/" + who)
    assert staff.get("/api/v1/notifications").json()["data"] == []


def test_release_delivery_revocation(browser, workspace, draft):
    url, rev = draft
    owner, manager = browser("owner"), browser("manager")
    manager.post(url + "/submit-for-internal-review", json=rev)
    manager.post(url + "/approve-and-release", json=rev)
    dashboard = owner.get(
        "/api/v1/dashboard/client", params={"client_id": str(workspace["north"])}
    ).json()["data"]
    assert len(dashboard["pending_approvals"]) == 1
    with Session(engine()) as db, db.begin():
        event = db.scalar(
            select(Outbox).where(Outbox.event_type == "content.client_review_requested")
        )
        event.attempts = 1
        run = WorkflowRun(
            event_id=event.id,
            workflow_name="WF-B",
            workflow_version="1.0",
            n8n_execution_id="14",
            attempt=1,
        )
        db.add(run)
        db.flush()
        workflows.deliver(db, run.id)
        workflows.deliver(db, run.id)
        assert db.scalar(select(func.count()).select_from(Notification)) == 2
    inbox = "/api/v1/notifications?portal=client"
    assert (
        len(owner.get(inbox).json()["data"]) == 1
        and browser("foreign").get(inbox).json()["data"] == []
    )
    from app.models import ClientMembership

    with Session(engine()) as db, db.begin():
        db.get(ClientMembership, workspace["owner_membership"]).is_active = False
    assert owner.get(inbox).json()["data"] == []
    assert browser("staff").get("/api/v1/automation/runs").status_code == 403


def test_release_delivery_survives_lost_ack(browser, workspace, draft):
    import time

    import pytest
    from fastapi import HTTPException
    from sqlalchemy import update

    url, rev = draft
    manager = browser("manager")
    manager.post(url + "/submit-for-internal-review", json=rev)
    manager.post(url + "/approve-and-release", json=rev)

    def register(db, raw, execution):
        stamp = str(int(time.time()))
        return workflows.start(
            db, raw, stamp, workflows.signature(stamp + "." + raw), execution, "WF-B"
        )

    with Session(engine()) as db, db.begin():
        db.execute(
            update(Outbox)
            .where(Outbox.event_type != "content.client_review_requested")
            .values(next_attempt_at=now() + timedelta(hours=1))
        )
        key, first, _, raw = workflows.claim(db)
        old = register(db, raw, "301")
        workflows.deliver(db, old)
    with Session(engine()) as db, db.begin():
        db.get_one(Outbox, key).claim_expires_at = now() - timedelta(seconds=1)
    with Session(engine()) as db, db.begin():
        _, second, _, raw = workflows.claim(db)
        assert first != second
        with pytest.raises(HTTPException) as err:
            workflows.finish(db, old)
        assert err.value.status_code == 409
        new = register(db, raw, "302")
        workflows.deliver(db, new)
        ack = workflows.finish(db, new)
        workflows.settle(db, key, first, None)
        workflows.settle(db, key, second, ack)
    with Session(engine()) as db:
        assert db.get_one(Outbox, key).status == "delivered"
        assert db.scalar(select(func.count()).select_from(Notification)) == 2
