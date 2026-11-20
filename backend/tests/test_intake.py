from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import engine
from app.models import Client, Project, User
from app.operations_models import Lead, Outbox

BASE = "/api/v1"
DATA = {"company_name": "Test Studio", "contact_name": "Dana", "email": "dana@example.com"}


def test_inquiry_access_and_ownership(browser, workspace):
    visitor = browser()
    for bad in [
        {"email": "invalid"},
        {"contact_name": " "},
        {"status": "converted"},
        {"website_confirmation": "spam"},
    ]:
        assert visitor.post(BASE + "/public/inquiries", json=DATA | bad).status_code == 422
    receipt = visitor.post(BASE + "/public/inquiries", json=DATA)
    assert receipt.status_code == 201 and set(receipt.json()["data"]) == {"id", "status", "message"}
    path = BASE + "/leads/" + receipt.json()["data"]["id"]
    manager = browser("manager")
    assert visitor.get(path).status_code == 401
    for role in ["staff", "owner", "foreign"]:
        session = browser(role)
        assert session.get(path).status_code == 403
        assert session.patch(path, json={"status": "qualified"}).status_code == 403
        assert session.post(path + "/convert", json={}).status_code == 403
    assert (
        manager.post(path + "/assign", json={"user_id": str(workspace["owner"])}).status_code == 422
    )
    assert (
        manager.post(path + "/assign", json={"user_id": str(workspace["staff"])}).status_code == 204
    )
    assert browser("staff").get(path).status_code == 403
    assert manager.post(path + "/convert", json={}).status_code == 409
    assert manager.post(path + "/reject").status_code == 204
    assert manager.patch(path, json={"status": "qualified"}).status_code == 409
    with Session(engine()) as db:
        assert db.scalar(select(func.count()).select_from(Lead)) == 1
        assert db.scalar(select(func.count()).select_from(Outbox)) == 1
        assert not db.scalar(select(User.id).where(User.email == DATA["email"]))


def test_conversion_and_onboarding(browser, workspace, test_password):
    manager = browser("manager")
    lead = manager.post(BASE + "/leads", json=DATA).json()["data"]["id"]
    path = BASE + "/leads/" + lead
    assert manager.patch(path, json={"status": "qualified"}).status_code == 200
    sessions = [manager, browser("admin")]
    barrier = Barrier(2)

    def convert(session):
        barrier.wait()
        result = session.post(
            path + "/convert",
            json={"create_initial_project": True, "initial_project_name": "Launch"},
        )
        assert result.status_code == 200
        return result.json()["data"]

    with ThreadPoolExecutor(2) as pool:
        a, b = pool.map(convert, sessions)
    assert a == b
    with Session(engine()) as db:
        assert (
            db.scalar(
                select(func.count()).select_from(Client).where(Client.company_name == "Test Studio")
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(Project)
                .where(Project.client_id == UUID(a["client_id"]))
            )
            == 1
        )
    inv = BASE + "/clients/" + a["client_id"] + "/invitations"
    assert (
        browser("owner")
        .post(inv, json={"role": "client_admin", "email": DATA["email"]})
        .status_code
        == 403
    )
    token = manager.post(inv, json={"role": "client_admin", "email": DATA["email"]}).json()["data"][
        "token"
    ]
    barrier = Barrier(2)

    def accept(guest):
        barrier.wait()
        return guest.post(
            BASE + "/auth/register",
            json={"token": token, "full_name": "Dana", "password": test_password[0]},
        ).status_code

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(accept, [browser(), browser()])) == [201, 400]
    client = browser("dana")
    assert client.get(BASE + "/clients/" + a["client_id"] + "/projects").json()["data"] == [
        {"id": a["project_id"], "name": "Launch"}
    ]
    assert client.get(BASE + "/clients/" + str(workspace["north"])).status_code == 404
    assert "token" not in manager.get(inv).text


def test_existing_invitee_and_revocation(browser, workspace):
    manager = browser("manager")
    path = BASE + "/clients/" + str(workspace["north"]) + "/invitations"
    data = {"email": "new@example.com", "role": "client_member"}
    invite = manager.post(path, json=data).json()["data"]
    redeem = BASE + "/auth/register"
    assert browser("owner").post(redeem, json={"token": invite["token"]}).status_code == 403
    assert browser().post(redeem, json={"token": invite["token"]}).status_code == 403
    assert manager.post(path + "/" + invite["id"] + "/revoke").status_code == 204
    target = browser("new")
    assert target.post(redeem, json={"token": invite["token"]}).status_code == 400
    token = manager.post(path, json=data).json()["data"]["token"]
    assert target.post(redeem, json={"token": token}).status_code == 201


def test_form_receipts(browser, monkeypatch):
    import secrets

    key = secrets.token_hex(32)
    monkeypatch.setenv("FORMS_KEY", key)
    settings.cache_clear()
    try:
        guest = browser()
        path = BASE + "/integrations/google-forms/submissions"
        data = {"source_submission_id": "synthetic-1", "inquiry": DATA}
        assert guest.post(path, json=data).status_code == 403
        headers = {"X-Forms-Key": key}
        result = guest.post(path, json=data, headers=headers)
        assert result.status_code == 200
        assert guest.post(path, json=data, headers=headers).json() == result.json()
        data["inquiry"] = DATA | {"contact_name": "Changed"}
        assert guest.post(path, json=data, headers=headers).status_code == 409
    finally:
        settings.cache_clear()
