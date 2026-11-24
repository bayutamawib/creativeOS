from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import Audit
from app.operations_models import Outbox
from app.project_models import TaskAssignee
from app.security import now
from app.services import tasks as task_service
from app.services import workflows
from app.services.reminders import day

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


def test_project_activity_scope_privacy_ordering_and_pagination(browser, workspace):
    manager, staff, owner, foreign = (
        browser(k) for k in ("manager", "staff", "owner", "foreign")
    )
    project = make(manager, workspace["north"])
    project_id = project.rsplit("/", 1)[-1]
    staff_id = str(workspace["staff"])
    manager.post(project + "/members", json={"user_id": staff_id})
    assigned = manager.post(project + "/tasks", json={"title": "Visible task"}).json()["data"]
    hidden = manager.post(project + "/tasks", json={"title": "Other task"}).json()["data"]
    manager.post(BASE + "/tasks/" + assigned["id"] + "/assign", json={"user_id": staff_id})
    manager.patch(BASE + "/tasks/" + assigned["id"], json={"status": "in_progress"})
    manager.patch(BASE + "/tasks/" + hidden["id"], json={"status": "blocked"})
    public_milestone = manager.post(
        project + "/milestones",
        json={"name": "Public launch", "client_visible": True},
    ).json()["data"]
    manager.post(
        project + "/milestones",
        json={"name": "Internal review", "client_visible": False},
    )
    with Session(engine()) as db, db.begin():
        db.add(
            Audit(
                actor_id=None,
                client_id=workspace["north"],
                project_id=project_id,
                action="project.updated",
                target_id=project_id,
                details={},
                created_at=now() + timedelta(seconds=1),
            )
        )

    first = manager.get(project + "/activity", params={"page_size": 2}).json()["data"]
    assert first["page"] == 1 and first["has_more"] is True
    assert len(first["items"]) == 2
    assert first["items"][0]["occurred_at"] >= first["items"][1]["occurred_at"]
    assert first["items"][0]["actor"] == "System"
    second = manager.get(project + "/activity", params={"page": 2, "page_size": 2}).json()[
        "data"
    ]
    assert second["page"] == 2 and second["items"]
    assert {row["id"] for row in first["items"]}.isdisjoint(
        {row["id"] for row in second["items"]}
    )

    staff_rows = staff.get(project + "/activity?portal=agency&page_size=100").json()["data"][
        "items"
    ]
    assert any("Visible task" in row["description"] for row in staff_rows)
    assert all("Other task" not in row["description"] for row in staff_rows)
    assert all(row["type"] != "task.assigned" or "Visible task" in row["description"] for row in staff_rows)

    client_response = owner.get(project + "/activity?portal=client&page_size=100")
    assert client_response.status_code == 200
    client_rows = client_response.json()["data"]["items"]
    assert any("Public launch" in row["description"] for row in client_rows)
    assert all("Internal review" not in row["description"] for row in client_rows)
    assert all(not row["type"].startswith("task.") for row in client_rows)
    assert all(not row["type"].startswith("project_member.") for row in client_rows)
    assert all(
        row["actor"] in {"Creative team", "owner"} for row in client_rows
    )
    assert public_milestone["id"]
    assert foreign.get(project + "/activity?portal=client").status_code == 404


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


def test_task_template_application_deadlines_duplicates_and_permissions(browser, workspace):
    manager, staff, owner, foreign = (
        browser(name) for name in ("manager", "staff", "owner", "foreign")
    )
    project = make(manager, workspace["north"])
    manager.post(project + "/members", json={"user_id": str(workspace["staff"])})
    payload = {
        "template": "social_media_campaign",
        "planning_start": "2026-12-01",
        "confirmed": True,
    }
    catalog = manager.get(BASE + "/task-templates")
    assert catalog.status_code == 200 and catalog.json()["data"][0]["steps"][0][
        "offset_days"
    ] == 2
    applied = manager.post(project + "/task-templates/apply", json=payload)
    assert applied.status_code == 201, applied.text
    rows = applied.json()["data"]
    assert len(rows) == 6
    assert rows[0]["title"] == "Creative brief approval"
    assert rows[0]["start_date"] == "2026-12-01" and rows[0]["due_date"] == "2026-12-03"
    assert rows[-1]["due_date"] == "2026-12-15"
    assert manager.post(project + "/task-templates/apply", json=payload).status_code == 409
    assert len(manager.get(project + "/tasks").json()["data"]) == 6
    assert staff.post(project + "/task-templates/apply", json=payload).status_code == 403
    assert owner.get(BASE + "/task-templates").status_code == 403
    assert owner.post(project + "/task-templates/apply", json=payload).status_code == 403
    assert foreign.post(project + "/task-templates/apply", json=payload).status_code == 403

    task = rows[0]
    assert staff.get(BASE + "/tasks/" + task["id"]).status_code == 404
    assert (
        manager.post(
            BASE + "/tasks/" + task["id"] + "/assign",
            json={"user_id": str(workspace["staff"])},
        ).status_code
        == 204
    )
    assert (
        staff.patch(
            BASE + "/tasks/" + task["id"],
            json={"description": "Unauthorized", "expected_updated_at": task["updated_at"]},
        ).status_code
        == 403
    )
    assert (
        staff.patch(
            BASE + "/tasks/" + task["id"],
            json={"status": "cancelled", "expected_updated_at": task["updated_at"]},
        ).status_code
        == 403
    )
    changed = manager.patch(
        BASE + "/tasks/" + task["id"],
        json={
            "description": "Updated planned activity",
            "due_date": "2026-12-04",
            "expected_updated_at": task["updated_at"],
        },
    )
    assert changed.status_code == 200
    assert (
        manager.patch(
            BASE + "/tasks/" + task["id"],
            json={"due_date": "2026-12-05", "expected_updated_at": task["updated_at"]},
        ).status_code
        == 409
    )
    current = changed.json()["data"]
    removed = manager.patch(
        BASE + "/tasks/" + task["id"],
        json={"status": "cancelled", "expected_updated_at": current["updated_at"]},
    )
    assert removed.status_code == 200 and removed.json()["data"]["status"] == "cancelled"
    with Session(engine()) as db:
        actions = list(
            db.scalars(
                select(Audit.action).where(
                    Audit.project_id == project.rsplit("/", 1)[-1],
                    Audit.action.in_(["task_template.applied", "task.updated"]),
                )
            )
        )
        assert "task_template.applied" in actions and actions.count("task.updated") >= 2


def test_task_template_rolls_back_if_a_step_fails(browser, workspace, monkeypatch):
    manager = browser("manager")
    project = make(manager, workspace["north"])
    original = task_service.create
    calls = 0

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("synthetic template failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(task_service, "create", fail_second)
    import pytest

    with pytest.raises(RuntimeError, match="synthetic template failure"):
        manager.post(
            project + "/task-templates/apply",
            json={
                "template": "social_media_campaign",
                "planning_start": "2026-12-01",
                "confirmed": True,
            },
        )
    assert manager.get(project + "/tasks").json()["data"] == []


def test_task_filters_overdue_scope_and_stale_status_update(browser, workspace):
    manager, admin, staff, owner = (browser(k) for k in ("manager", "admin", "staff", "owner"))
    project = make(manager, workspace["north"])
    staff_id = str(workspace["staff"])
    manager.post(project + "/members", json={"user_id": staff_id})
    today = day(now())
    overdue = manager.post(
        project + "/tasks",
        json={
            "title": "Overdue urgent board task",
            "priority": "urgent",
            "due_date": str(today - timedelta(days=1)),
        },
    ).json()["data"]
    future = manager.post(
        project + "/tasks",
        json={
            "title": "Future board task",
            "priority": "low",
            "due_date": str(today + timedelta(days=2)),
        },
    ).json()["data"]
    for task in (overdue, future):
        assert manager.post(
            BASE + "/tasks/" + task["id"] + "/assign", json={"user_id": staff_id}
        ).status_code == 204

    filtered = manager.get(
        BASE + "/tasks",
        params={
            "project_id": project.rsplit("/", 1)[-1],
            "status": "todo",
            "priority": "urgent",
            "assignee_id": staff_id,
            "overdue": "true",
        },
    ).json()["data"]
    assert [task["id"] for task in filtered] == [overdue["id"]]
    assert filtered[0]["is_overdue"] is True
    assert [
        task["id"]
        for task in manager.get(BASE + "/tasks", params={"overdue": "false"}).json()["data"]
    ].count(future["id"]) == 1
    assert [task["id"] for task in staff.get(BASE + "/tasks").json()["data"]] == [
        overdue["id"],
        future["id"],
    ]
    assert owner.get(BASE + "/tasks", params={"project_id": project.rsplit("/", 1)[-1]}).status_code == 403
    assert manager.get(
        BASE + "/tasks", params={"due_from": str(today), "due_to": str(today - timedelta(days=1))}
    ).status_code == 422

    barrier = Barrier(2)

    def move(client, status):
        barrier.wait()
        return client.patch(
            BASE + "/tasks/" + overdue["id"],
            json={"status": status, "expected_updated_at": overdue["updated_at"]},
        ).status_code

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda args: move(*args), [(staff, "in_progress"), (admin, "blocked")]))
    assert sorted(results) == [200, 409]


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
