import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.providers import Fixture, Response
from app.ai.runner import execute_one
from app.ai_models import Generation
from app.db import engine
from app.models import Audit
from app.operations_models import Outbox
from app.project_models import Milestone, ProjectMember, Task
from app.report_models import Report
from app.security import now
from app.services import reports

BASE = "/api/v1"
PERIOD = {"period_start": "2026-03-08", "period_end": "2026-03-08"}


def test_period_metrics_and_concurrent_reservation(workspace, browser, monkeypatch):
    from app.config import settings

    monkeypatch.setenv("AGENCY_TIMEZONE", "America/New_York")
    settings.cache_clear()
    p = workspace["north-1"]
    path = f"{BASE}/projects/{p}/reports/generate"
    managers = [browser("manager"), browser("admin")]
    assert (
        managers[0]
        .post(path, json={"period_start": "2026-03-09", "period_end": "2026-03-08"})
        .status_code
        == 422
    )
    lo, hi = reports.bounds(date(2026, 3, 8), date(2026, 3, 8), ZoneInfo("America/New_York"))
    assert (hi.timestamp() - lo.timestamp()) / 3600 == 23
    with Session(engine()) as db, db.begin():
        for dt in (lo - timedelta(seconds=1), lo, hi - timedelta(seconds=1), hi):
            db.add(
                Task(
                    project_id=p,
                    client_id=workspace["north"],
                    title="private",
                    created_by=workspace["admin"],
                    status="completed",
                    completed_at=dt,
                )
            )
        db.add(
            Task(
                project_id=p,
                client_id=workspace["north"],
                title="private",
                created_by=workspace["admin"],
                status="in_progress",
                due_date=date(2026, 3, 8),
            )
        )
        db.add(
            Task(
                project_id=workspace["north-2"],
                client_id=workspace["north"],
                title="other project",
                created_by=workspace["admin"],
            )
        )
        for visible, status in [(True, "completed"), (True, "pending"), (False, "completed")]:
            db.add(
                Milestone(
                    project_id=p,
                    name="milestone",
                    client_visible=visible,
                    status=status,
                    completed_at=lo if status == "completed" else None,
                )
            )
    with ThreadPoolExecutor(2) as pool:
        rs = list(pool.map(lambda c: c.post(path, json=PERIOD), managers))
    assert all(r.status_code == 202 for r in rs)
    rows = [r.json()["data"] for r in rs]
    assert rows[0]["id"] == rows[1]["id"]
    m = rows[0]["metrics"]
    assert [
        m[k]
        for k in (
            "total_tasks",
            "completed_tasks",
            "open_tasks",
            "in_progress_tasks",
            "deadlines_in_period",
            "visible_milestones",
            "completed_visible_milestones",
            "progress_percent",
            "milestones_completed_in_period",
        )
    ] == [5, 2, 1, 1, 1, 2, 1, 50, 1]
    assert rows[0]["provenance"]["start_inclusive"].endswith("-05:00") and rows[0]["provenance"][
        "end_exclusive"
    ].endswith("-04:00")
    with Session(engine()) as db:
        assert db.scalar(select(func.count()).select_from(Generation)) == 1


def test_report_states_and_isolation(workspace, browser):
    manager, owner, foreign, staff = [browser(n) for n in ("manager", "owner", "foreign", "staff")]
    project = workspace["north-1"]
    gen = f"{BASE}/projects/{project}/reports/generate"
    with Session(engine()) as db, db.begin():
        db.add(ProjectMember(project_id=project, user_id=workspace["staff"]))
    assert staff.post(gen, json=PERIOD).status_code == 403
    row = manager.post(gen, json=PERIOD).json()["data"]
    path = f"{BASE}/reports/{row['id']}"
    for client in (owner, foreign):
        assert (
            client.get(path).status_code == 404
            and client.get(path + "/download").status_code == 404
        )
        assert client.get(BASE + "/reports").json()["data"] == []
        assert client.get(BASE + "/agency/reports/operations").status_code == 403
    assert execute_one()
    draft = manager.get(path).json()["data"]
    assert draft["status"] == "draft" and "Completed tasks: 0" in draft["narrative"]
    assert manager.post(path + "/publish", json={"version": 1}).status_code == 409
    assert staff.post(path + "/submit-for-review", json={"version": 1}).status_code == 403
    assert (
        manager.post(path + "/submit-for-review", json={"version": 1}).json()["data"]["status"]
        == "ready_for_review"
    )
    assert owner.get(path + "/download").status_code == 404
    assert (
        manager.patch(path, json={"version": 2, "narrative": "Reviewed project summary."}).json()[
            "data"
        ]["status"]
        == "draft"
    )
    assert manager.post(path + "/publish", json={"version": 2}).status_code == 409
    assert manager.post(path + "/submit-for-review", json={"version": 3}).status_code == 200
    for client in (staff, owner, foreign):
        assert client.post(path + "/publish", json={"version": 4}).status_code == 403
    admins = [manager, browser("admin")]
    with ThreadPoolExecutor(2) as pool:
        assert sorted(
            pool.map(lambda c: c.post(path + "/publish", json={"version": 4}).status_code, admins)
        ) == [200, 409]
    assert owner.get(path + "/download").json()["narrative"] == "Reviewed project summary."
    assert len(owner.get(BASE + "/reports").json()["data"]) == 1
    assert (
        foreign.get(path).status_code == 404 and foreign.get(path + "/download").status_code == 404
    )
    assert owner.get(f"{BASE}/projects/{workspace['north-2']}/reports").json()["data"] == []
    assert manager.patch(path, json={"version": 5, "narrative": "replacement"}).status_code == 409
    with Session(engine()) as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Outbox)
                .where(Outbox.event_type == "report.published")
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count()).select_from(Audit).where(Audit.action == "report.publish")
            )
            == 1
        )


def test_failed_summary_reuses_frozen_evidence(workspace, browser):
    manager = browser("manager")
    p = workspace["north-1"]
    path = f"{BASE}/projects/{p}/reports/generate"
    original = manager.post(path, json=PERIOD).json()["data"]

    class Unsupported(Fixture):
        def generate(self, kind, model, context, params):
            value = json.loads(super().generate(kind, model, context, params).content)
            value["risks"] = ["Revenue doubled."]
            return Response(json.dumps(value))

    for _ in range(3):
        assert execute_one(Unsupported())
        with Session(engine()) as db, db.begin():
            job = db.scalars(select(Generation)).one()
            job.next_attempt_at = now()
    with Session(engine()) as db, db.begin():
        assert db.get_one(Report, UUID(original["id"])).status == "failed"
        assert db.scalars(select(Generation)).one().error_code == "unsupported_report_claim"
        db.add(
            Task(
                project_id=p,
                client_id=workspace["north"],
                created_by=workspace["manager"],
                title="later",
            )
        )
    retry = manager.post(path, json=PERIOD).json()["data"]
    assert retry["id"] == original["id"] and retry["metrics"] == original["metrics"]
    assert execute_one()
    assert manager.get(BASE + "/reports/" + retry["id"]).json()["data"]["status"] == "draft"


def test_signed_revision_counts_in_report(workspace, browser):
    from test_reviews import build_draft

    from app.services.reminders import day

    # Construct an actual reviewed revision through the same operations as the client journey.
    path, revision = build_draft(browser, workspace)
    manager, owner = browser("manager"), browser("owner")
    assert manager.post(path + "/submit-for-internal-review", json=revision).status_code == 200
    assert manager.post(path + "/approve-and-release", json=revision).status_code == 200
    assert (
        owner.post(
            path + "/request-revision", json=revision | {"comments": "Please revise"}
        ).status_code
        == 200
    )
    today = str(day(now()))
    row = manager.post(
        f"{BASE}/projects/{workspace['north-1']}/reports/generate",
        json={"period_start": today, "period_end": today},
    ).json()["data"]
    assert row["metrics"]["revisions_requested_in_period"] == 1
    assert row["metrics"]["approvals_in_period"] == row["metrics"]["awaiting_client_approval"] == 0


def test_delayed_schedule_replay_retains_original_week(workspace):
    from datetime import UTC, datetime

    from app.models import Project
    from app.services import report_schedule

    with Session(engine()) as db, db.begin():
        db.get_one(Project, workspace["north-1"]).status = "in_progress"
        tick = datetime(2026, 11, 15, 17, 0, tzinfo=UTC)
        key = report_schedule.register(db, "751", tick)
        assert report_schedule.status(db, key, enqueue=True)["status"] == "running"
        assert report_schedule.register(db, "751", tick + timedelta(days=7)) == key
        assert report_schedule.status(db, key, enqueue=True)["status"] == "running"
        assert db.scalar(select(func.count()).select_from(Report)) == 1
    assert execute_one()
    with Session(engine()) as db, db.begin():
        assert report_schedule.status(db, key, enqueue=False)["status"] == "completed"
        r = db.scalars(select(Report)).one()
        assert r.period_start == date(2026, 11, 9) and r.period_end == date(2026, 11, 15)
