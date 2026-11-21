from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import Audit
from app.operations_models import Outbox
from app.project_models import TaskAssignee
from app.services import workflows

BASE = "/api/v1"


def make(manager, client):
    res = manager.post(
        BASE + "/projects",
        json={
            "name": "Launch",
            "client_id": str(client),
            "description": "Agency only",
            "budget": "499.95",
        },
    )
    assert res.status_code == 201, res.text
    return BASE + "/projects/" + res.json()["data"]["id"]


def test_project_crud_scope_and_archive(browser, workspace):
    manager, owner, foreign, staff = (browser(k) for k in ("manager", "owner", "foreign", "staff"))
    p = make(manager, workspace["north"])
    assert (
        owner.post(
            BASE + "/projects", json={"name": "X", "client_id": str(workspace["north"])}
        ).status_code
        == 403
    )
    assert staff.get(p).status_code == 404
    assert foreign.get(p).status_code == 404
    assert browser().get(p).status_code == 401
    assert manager.patch(p, json={"client_id": str(workspace["south"])}).status_code == 422
    assert (
        manager.patch(p, json={"start_date": "2026-12-05", "due_date": "2026-12-01"}).status_code
        == 422
    )
    assert (
        manager.patch(
            p, json={"name": "Revised", "status": "planning", "due_date": "2026-12-15"}
        ).status_code
        == 200
    )
    safe = owner.get(p).json()["data"]
    assert (
        safe["name"] == "Revised"
        and not {"description", "budget", "created_by", "priority"} & safe.keys()
    )
    assert owner.get(p + "/tasks").status_code == 403
    assert owner.get(p + "/members").status_code == 403
    assert all(
        r["client_id"] == str(workspace["north"])
        for r in owner.get(BASE + "/projects").json()["data"]
    )
    assert (
        manager.post(p + "/members", json={"user_id": str(workspace["member"])}).status_code == 422
    )
    assert (
        manager.post(p + "/members", json={"user_id": str(workspace["staff"])}).status_code == 204
    )
    assert staff.get(p + "?portal=agency").status_code == 200
    assert staff.get(p + "?portal=client").status_code == 404
    assert staff.patch(p, json={"name": "Wrong"}).status_code == 403
    assert [r["id"] for r in staff.get(BASE + "/projects?portal=agency").json()["data"]] == [
        safe["id"]
    ]
    assert manager.post(p + "/archive").status_code == 204
    assert manager.post(p + "/archive").status_code == 204
    assert owner.get(p).status_code == 404 and staff.get(p).status_code == 404
    assert (
        safe["id"] not in owner.get(BASE + "/clients/" + str(workspace["north"]) + "/projects").text
    )
    assert owner.get(p + "/approval-authority").status_code == 404
    with Session(engine()) as db:
        assert (
            db.scalar(
                select(func.count()).select_from(Audit).where(Audit.action == "project.archived")
            )
            == 1
        )


def test_milestone_release_and_progress(browser, workspace):
    admin, owner, foreign = (browser(k) for k in ("admin", "owner", "foreign"))
    p = make(admin, workspace["north"])
    assert owner.get(p + "/progress").json()["data"]["percent"] == 0
    for name, state, release in [
        ("First", "completed", True),
        ("Second", "in_progress", True),
        ("Private", "completed", False),
    ]:
        created = admin.post(
            p + "/milestones",
            json={
                "name": name,
                "status": state,
                "description": "Internal",
                "client_visible": release,
            },
        )
        assert created.status_code == 201, created.text
        if name == "Second":
            second = created.json()["data"]["id"]
    assert admin.get(p + "/progress").json()["data"]["percent"] == 67
    assert owner.get(p + "/progress").json()["data"] == {
        "percent": 50,
        "total_milestones": 2,
        "completed_milestones": 1,
    }
    client_list = owner.get(BASE + "/projects", params={"q": "Launch", "status": "draft"}).json()[
        "data"
    ]
    assert len(client_list) == 1 and client_list[0]["next_milestone"] == "Second"
    assert client_list[0]["progress"]["total_milestones"] == 2
    rows = owner.get(p + "/milestones").json()["data"]
    assert {r["name"] for r in rows} == {"First", "Second"} and all(
        "description" not in r for r in rows
    )
    assert foreign.get(p + "/progress").status_code == 404
    assert (
        owner.patch(BASE + "/milestones/" + second, json={"status": "completed"}).status_code == 403
    )
    assert admin.patch(BASE + "/milestones/" + second, json={"status": "completed"}).json()["data"][
        "completed_at"
    ]
    assert owner.get(p + "/progress").json()["data"]["percent"] == 100


def test_task_lifecycle_memberships_and_concurrent_events(browser, workspace):
    manager, admin, staff, owner = (browser(k) for k in ("manager", "admin", "staff", "owner"))
    p = make(manager, workspace["north"])
    staff_id = str(workspace["staff"])
    foreign_milestone = admin.post(
        BASE + "/projects/" + str(workspace["south-1"]) + "/milestones", json={"name": "Elsewhere"}
    ).json()["data"]["id"]
    assert (
        manager.post(
            p + "/tasks", json={"title": "Wrong", "milestone_id": foreign_milestone}
        ).status_code
        == 422
    )
    result = manager.post(
        p + "/tasks",
        json={
            "title": "Internal layout",
            "description": "Unreleased",
            "start_date": "2026-12-01",
            "due_date": "2026-12-15",
        },
    )
    assert result.status_code == 201, result.text
    t = BASE + "/tasks/" + result.json()["data"]["id"]
    assert manager.post(t + "/assign", json={"user_id": staff_id}).status_code == 422
    assert manager.post(p + "/members", json={"user_id": staff_id}).status_code == 204
    assert staff.get(t).status_code == 404 and not staff.get(p + "/tasks").json()["data"]
    assert owner.get(t).status_code == 403 and owner.get(BASE + "/tasks").status_code == 403
    barrier = Barrier(2)

    def assign(client):
        barrier.wait()
        return client.post(t + "/assign", json={"user_id": staff_id}).status_code

    with ThreadPoolExecutor(2) as pool:
        assert list(pool.map(assign, [admin, manager])) == [204, 204]
    with Session(engine()) as db:
        assert db.scalar(select(func.count()).select_from(TaskAssignee)) == 1
        events = list(db.scalars(select(Outbox).where(Outbox.event_type == "task.assigned")))
        assert len(events) == 1 and workflows.eligible(db, events[0])[0] == {workspace["staff"]}
    assert staff.get(t).status_code == 200
    assert staff.patch(t, json={"due_date": "2026-12-12"}).status_code == 403
    assert manager.patch(t, json={"due_date": "2026-11-28"}).status_code == 422
    assert staff.post(t + "/assign", json={"user_id": staff_id}).status_code == 403
    for state in ["in_progress", "blocked", "in_review"]:
        assert staff.patch(t, json={"status": state}).json()["data"]["status"] == state
    assert staff.post(t + "/complete").json()["data"]["completed_at"]
    assert staff.patch(t, json={"status": "in_progress"}).status_code == 409
    assert admin.patch(t, json={"status": "todo"}).json()["data"]["completed_at"] is None
    assert manager.delete(p + "/members/" + staff_id).status_code == 204
    assert staff.get(t).status_code == 404 and staff.get(p).status_code == 404
    assert staff.get(BASE + "/tasks").json()["data"] == []
    with Session(engine()) as db:
        assert not db.scalar(select(TaskAssignee.id))
        assert workflows.eligible(db, db.get_one(Outbox, events[0].id))[0] == set()


def test_task_workflow_delivery_and_inbox(browser, workspace):
    import time

    from app.config import settings

    manager, staff, owner = (browser(k) for k in ("manager", "staff", "owner"))
    p = make(manager, workspace["north"])
    staff_id = str(workspace["staff"])
    manager.post(p + "/members", json={"user_id": staff_id})
    tid = manager.post(p + "/tasks", json={"title": "Production"}).json()["data"]["id"]
    manager.post(BASE + "/tasks/" + tid + "/assign", json={"user_id": staff_id})
    with Session(engine()) as db, db.begin():
        _, _, _, raw = workflows.claim(db)
    stamp = str(int(time.time()))
    payload = {
        "raw": raw,
        "timestamp": stamp,
        "signature": workflows.signature(stamp + "." + raw),
        "workflow": "WF-C",
        "execution_id": "23",
    }
    headers = {"X-Creative-Service": workflows.secret(settings().workflow_key)}
    service = browser()
    start = BASE + "/internal/workflow-runs"
    run = service.post(start, json=payload, headers=headers).json()["run_id"]
    for _ in range(2):
        assert (
            service.post(start + "/" + run + "/notifications", headers=headers).status_code == 200
        )
    assert [n["resource_id"] for n in staff.get(BASE + "/notifications").json()["data"]] == [tid]
    assert manager.get(BASE + "/notifications").json()["data"] == []
    assert owner.get(BASE + "/notifications").status_code == 403
    manager.delete(p + "/members/" + staff_id)
    assert staff.get(BASE + "/notifications").json()["data"] == []


def test_database_rejects_cross_client_task(workspace):
    import pytest
    from sqlalchemy.exc import IntegrityError

    from app.project_models import Task

    with pytest.raises(IntegrityError), Session(engine()) as db, db.begin():
        db.add(
            Task(
                project_id=workspace["north-1"],
                client_id=workspace["south"],
                title="Invalid ownership",
                created_by=workspace["admin"],
            )
        )
        db.flush()


def test_client_member_directory_scope(browser, workspace):
    path = BASE + "/clients/" + str(workspace["north"]) + "/members"
    assert browser("manager").get(path).status_code == 200
    assert browser("owner").get(path + "?portal=client").status_code == 200
    assert browser("member").get(path + "?portal=client").status_code == 403
    assert browser("foreign").get(path + "?portal=client").status_code == 404


def test_project_pagination_applies_after_client_scope(browser, workspace):
    client = browser("owner")
    url = "/api/v1/projects?portal=client&page_size=1&page="
    pages = [client.get(url + str(i)).json()["data"] for i in (1, 2, 3)]
    assert [len(page) for page in pages] == [1, 1, 0]
    assert {row["id"] for page in pages for row in page} == {
        str(workspace["north-1"]),
        str(workspace["north-2"]),
    }
    assert client.get(url + "0").status_code == 422
    assert client.get("/api/v1/projects?page_size=101").status_code == 422
