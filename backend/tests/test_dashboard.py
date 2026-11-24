from datetime import timedelta

from app.security import now
from app.services.reminders import day

BASE = "/api/v1"


def test_authorized_operations_and_client_dashboard(browser, workspace):
    manager, staff, owner, foreign = (
        browser(name) for name in ("manager", "staff", "owner", "foreign")
    )
    project = f"{BASE}/projects/{workspace['north-1']}"
    manager.post(project + "/members", json={"user_id": str(workspace["staff"])})
    manager.post(
        project + "/milestones",
        json={"name": "Shared launch", "status": "in_progress", "client_visible": True},
    )
    manager.post(
        project + "/milestones",
        json={"name": "Private QA", "status": "pending", "client_visible": False},
    )
    owner.post(
        project + "/briefs?portal=client",
        json={"title": "Launch requirements", "objective": "Introduce the new service."},
    )
    due = str(day(now()) - timedelta(days=1))
    assigned = manager.post(
        project + "/tasks", json={"title": "Assigned overdue", "due_date": due}
    ).json()["data"]
    completed = manager.post(project + "/tasks", json={"title": "Completed work"}).json()[
        "data"
    ]
    manager.post(
        f"{BASE}/tasks/{assigned['id']}/assign", json={"user_id": str(workspace["staff"])}
    )
    manager.post(f"{BASE}/tasks/{completed['id']}/complete")

    agency = manager.get(BASE + "/dashboard/agency")
    assert agency.status_code == 200
    metrics = agency.json()["data"]
    assert metrics["open_tasks"] >= 1
    assert metrics["overdue_tasks"] >= 1
    assert metrics["task_completion_rate"] == 50
    assert any(row["assignee"] == "staff" for row in metrics["workload"])
    assert any(row["name"] == "north-1" for row in metrics["projects"])

    staff_metrics = staff.get(BASE + "/dashboard/agency").json()["data"]
    assert staff_metrics["open_tasks"] == 1 and staff_metrics["overdue_tasks"] == 1
    assert {row["assignee"] for row in staff_metrics["workload"]} == {"staff"}
    assert owner.get(BASE + "/dashboard/agency").status_code == 403

    client = owner.get(
        BASE + "/dashboard/client", params={"client_id": str(workspace["north"])}
    )
    assert client.status_code == 200
    safe = client.json()["data"]
    assert any(row["title"] == "Launch requirements" for row in safe["briefs"])
    assert any(row["name"] == "Shared launch" for row in safe["milestones"])
    assert all(row["name"] != "Private QA" for row in safe["milestones"])
    assert not {"tasks", "workload", "assignees"} & safe.keys()
    assert (
        foreign.get(
            BASE + "/dashboard/client", params={"client_id": str(workspace["north"])}
        ).status_code
        == 404
    )
