from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_studio import approved, request

from app.ai import runner
from app.ai_models import ContentItem
from app.db import engine
from app.models import Audit, ClientMembership
from app.operations_models import Outbox
from app.review_models import Review
from app.services import reviews


@pytest.fixture
def draft(browser, workspace):
    return build_draft(browser, workspace)


def build_draft(browser, workspace):
    manager, owner = browser("manager"), browser("owner")
    pid = workspace["north-1"]
    path, _ = approved(owner, manager, pid)
    for action in ["analyze", "generate-creative-direction"]:
        assert request(manager, path, action).status_code == 202 and runner.execute_one()
    direction = manager.get(path + "/proposals").json()["data"][0]["id"]
    manager.post("/api/v1/proposals/" + direction + "/approve")
    assert (
        request(
            manager, path, "generate-content-plan", {"direction_proposal_id": direction}
        ).status_code
        == 202
        and runner.execute_one()
    )
    proposal = next(
        p["id"] for p in manager.get(path + "/proposals").json()["data"] if p["kind"] == "plan_item"
    )
    manager.post("/api/v1/proposals/" + proposal + "/approve")
    item = manager.post(
        f"/api/v1/projects/{pid}/content-items", json={"proposal_id": proposal}
    ).json()["data"]
    return "/api/v1/content-items/" + item["id"], {"revision_id": item["current_revision_id"]}


def race(left, right):
    gate = Barrier(2)

    def run(callback):
        gate.wait()
        return callback().status_code

    with ThreadPoolExecutor(2) as pool:
        return list(pool.map(run, [left, right]))


@pytest.mark.parametrize(
    "signer,decision",
    [
        ("owner", "client-approval"),
        ("owner", "request-revision"),
        ("member", "client-approval"),
        ("member", "request-revision"),
    ],
)
def test_signers(browser, workspace, draft, signer, decision):
    url, rev = draft
    manager, owner, member, foreign, staff = [
        browser(n) for n in ("manager", "owner", "member", "foreign", "staff")
    ]
    assert staff.post(url + "/submit-for-internal-review", json=rev).status_code == 404
    pid = workspace["north-1"]
    manager.post(f"/api/v1/projects/{pid}/members", json={"user_id": str(workspace["staff"])})
    assert staff.post(url + "/submit-for-internal-review", json=rev).status_code == 200
    assert staff.post(url + "/approve-and-release", json=rev).status_code == 403
    assert owner.get(url).status_code == 403
    assert (
        manager.post(
            url + "/approve-and-release", json=rev | {"comments": "Private notes"}
        ).status_code
        == 200
    )
    assert "Private notes" not in owner.get(url).text
    assert (
        foreign.get(url).status_code == 404
        and foreign.post(url + "/" + decision, json=rev).status_code == 404
    )
    assert (
        member.post(
            url + "/feedback", json=rev | {"message": "A comment", "visibility": "client_visible"}
        ).status_code
        == 200
    )
    for action in ["request-revision", "client-approval"]:
        assert (
            member.post(url + "/" + action, json=rev | {"comments": "Please revise"}).status_code
            == 403
        )
    grant = f"/api/v1/projects/{pid}/approval-delegations/{workspace['member_membership']}"
    other = grant.replace(str(pid), str(workspace["north-2"]))
    owner.put(other)
    assert member.post(url + "/" + decision, json=rev).status_code == 403
    owner.put(grant)
    owner.delete(grant)
    assert member.post(url + "/" + decision, json=rev).status_code == 403
    owner.put(grant)
    data = rev | {"comments": "Please review the headline"}
    client = member if signer == "member" else owner
    assert client.post(url + "/" + decision, json=data).status_code == 200
    assert client.post(url + "/" + decision, json=data).status_code == 409
    with Session(engine()) as db:
        row = db.scalar(select(Review).where(Review.stage == "client"))
        assert row.membership_id == workspace[signer + "_membership"] and bool(
            row.delegation_id
        ) == (signer == "member")


def test_races_rollback_and_supersession(browser, workspace, draft):
    url, rev = draft
    manager, admin, owner = browser("manager"), browser("admin"), browser("owner")
    manager.post(url + "/submit-for-internal-review", json=rev)
    key = UUID(url.rsplit("/", 1)[1])
    with pytest.raises(RuntimeError), Session(engine()) as db, db.begin():
        reviews.transition(
            db, workspace["manager"], key, UUID(rev["revision_id"]), "approve-and-release", None
        )
        db.flush()
        raise RuntimeError("abort before commit")
    with Session(engine()) as db:
        assert db.get(ContentItem, key).status == "internal_review"
        for model, predicate in [
            (Review, Review.stage == "client"),
            (Audit, Audit.action == "content.approve-and-release"),
            (Outbox, Outbox.event_type == "content.client_review_requested"),
        ]:
            assert db.scalar(select(func.count()).select_from(model).where(predicate)) == 0
    assert sorted(
        race(
            lambda: manager.post(url + "/approve-and-release", json=rev),
            lambda: admin.post(url + "/approve-and-release", json=rev),
        )
    ) == [200, 409]
    manager.post(
        url + "/revisions",
        json=rev | {"headline": "Private revised title", "caption": "Next draft"},
    )
    assert (
        "Private revised title" not in owner.get(url).text
        and owner.get(url).json()["data"]["status"] == "superseded"
    )
    assert owner.post(url + "/client-approval", json=rev).status_code == 409
    rev = {"revision_id": manager.get(url).json()["data"]["current_revision_id"]}
    manager.post(url + "/submit-for-internal-review", json=rev)
    manager.post(url + "/approve-and-release", json=rev)
    member = browser("member")
    grant = f"/api/v1/projects/{workspace['north-1']}/approval-delegations/{workspace['member_membership']}"
    owner.put(grant)
    with Session(engine()) as db, db.begin():
        db.get(ClientMembership, workspace["member_membership"]).is_active = False
    assert member.post(url + "/client-approval", json=rev).status_code == 404
    second = browser("owner")
    assert sorted(
        race(
            lambda: owner.post(url + "/client-approval", json=rev),
            lambda: second.post(url + "/request-revision", json=rev | {"comments": "Change this"}),
        )
    ) == [200, 409]


def test_file_release_and_revocation_race(browser, workspace, draft):
    manager, owner, member = browser("manager"), browser("owner"), browser("member")
    url, rev = draft

    def upload(pid):
        res = manager.post(
            "/api/v1/files/upload",
            params={"project_id": str(pid), "file_name": "layout.txt"},
            content=b"Private layout",
            headers={"Content-Type": "text/plain"},
        )
        return res.json()["data"]["id"]

    f = upload(workspace["north-1"])
    wrong = upload(workspace["north-2"])
    edit = rev | {"headline": "Headline", "caption": "Copy"}
    assert (
        manager.post(url + "/revisions", json=edit | {"attachment_ids": [wrong]}).status_code == 422
    )
    assert manager.post(url + "/revisions", json=edit | {"attachment_ids": [f]}).status_code == 201
    rev = {"revision_id": manager.get(url).json()["data"]["current_revision_id"]}
    download = "/api/v1/files/" + f + "/download"
    assert owner.get(download).status_code == 404
    manager.post(url + "/submit-for-internal-review", json=rev)
    assert (
        manager.post(
            url + "/request-internal-changes", json=rev | {"comments": "Improve the layout"}
        ).status_code
        == 200
    )
    assert owner.get(download).status_code == 404
    manager.post(url + "/revisions", json=edit | rev)
    rev = {"revision_id": manager.get(url).json()["data"]["current_revision_id"]}
    manager.post(url + "/submit-for-internal-review", json=rev)
    assert manager.post(url + "/approve-and-release", json=rev).status_code == 200
    assert owner.get(download).content == b"Private layout"
    assert browser("foreign").get(download).status_code == 404
    grant = f"/api/v1/projects/{workspace['north-1']}/approval-delegations/{workspace['member_membership']}"
    owner.put(grant)
    revoke, decision = race(
        lambda: owner.delete(grant), lambda: member.post(url + "/client-approval", json=rev)
    )
    assert revoke == 204 and decision in {200, 403}
    assert member.post(url + "/client-approval", json=rev).status_code == 403


def test_conflicting_internal_decisions(browser, workspace, draft):
    from app.config import settings
    from app.services.workflows import secret

    url, rev = draft
    manager, admin = browser("manager"), browser("admin")
    manager.post(url + "/submit-for-internal-review", json=rev)
    header = {"X-Creative-Service": secret(settings().workflow_key)}
    assert browser().post(url + "/approve-and-release", json=rev, headers=header).status_code == 401
    release, changes = race(
        lambda: manager.post(url + "/approve-and-release", json=rev),
        lambda: admin.post(
            url + "/request-internal-changes", json=rev | {"comments": "Adjust caption"}
        ),
    )
    assert sorted([release, changes]) == [200, 409]
    with Session(engine()) as db:
        review = db.scalar(select(Review).where(Review.stage == "internal"))
        assert review.decision == ("approved" if release == 200 else "revision_requested")
        assert db.scalar(
            select(func.count()).select_from(Review).where(Review.stage == "client")
        ) == int(release == 200)
        assert db.scalar(
            select(func.count())
            .select_from(Outbox)
            .where(Outbox.event_type == "content.client_review_requested")
        ) == int(release == 200)


def test_queue_query_count_with_additional_revisions(browser, workspace, draft):
    from sqlalchemy import event

    manager = browser("manager")
    url, rev = draft
    counts = []
    queries = []

    def record(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    for number in range(1, 5):
        queries.clear()

        event.listen(engine(), "before_cursor_execute", record)
        try:
            rows = manager.get("/api/v1/approvals?portal=agency").json()["data"]
        finally:
            event.remove(engine(), "before_cursor_execute", record)
        assert len(rows[0]["history"]) == number
        counts.append(len(queries))
        if number < 4:
            res = manager.post(
                url + "/revisions",
                json={**rev, "headline": "Revised title", "caption": "Revised caption"},
            )
            assert res.status_code in {200, 201}, res.text
            rev = {"revision_id": manager.get(url).json()["data"]["current_revision_id"]}
    assert len(set(counts)) == 1
