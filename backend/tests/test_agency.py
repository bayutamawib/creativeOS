import secrets
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import AgencyInvitation, AgencyMembership, Audit, User
from app.security import digest

AGENCY = "/api/v1/agency"
REGISTER = "/api/v1/auth/register"


def role(ids, name, value):
    return f"{AGENCY}/members/{ids[name]}/roles/{value}"


@pytest.mark.parametrize("value", ["team_member", "agency_manager", "admin"])
def test_admin_role_lifecycle(browser, workspace, value):
    admin = browser("admin")
    url = role(workspace, "new", value)
    assert admin.put(url).status_code == 204
    assert admin.patch(url, json={"is_active": False}).status_code == 204
    assert admin.patch(url, json={"is_active": True}).status_code == 204
    assert admin.delete(url).status_code == 204
    assert admin.delete(url).status_code == 204
    with Session(engine()) as db:
        assert db.scalar(select(func.count()).select_from(Audit)) == 4


def test_manager_boundaries_and_client_access_survive(browser, workspace):
    manager, staff = browser("manager"), browser("staff")
    url = role(workspace, "staff", "team_member")
    assert manager.patch(url, json={"is_active": False}).status_code == 204
    assert staff.get("/api/v1/auth/me").json()["data"]["agency_roles"] == []
    assert staff.get(f"/api/v1/clients/{workspace['south']}").status_code == 200
    assert manager.patch(url, json={"is_active": True}).status_code == 204
    assert manager.delete(url).status_code == 204
    assert manager.put(url).status_code == 204
    for value in ("admin", "agency_manager"):
        assert manager.put(role(workspace, "staff", value)).status_code == 403
        assert (
            manager.post(
                AGENCY + "/invitations", json={"email": "new@example.com", "role": value}
            ).status_code
            == 403
        )
    for target in ("admin", "manager"):
        for method in ("put", "delete"):
            assert (
                getattr(manager, method)(role(workspace, target, "team_member")).status_code == 403
            )
    admin = browser("admin")
    elevated = role(workspace, "staff", "agency_manager")
    assert admin.put(elevated).status_code == 204
    assert admin.patch(elevated, json={"is_active": False}).status_code == 204
    assert manager.delete(url).status_code == 403
    assert (
        manager.patch(
            AGENCY + f"/members/{workspace['admin']}/account", json={"is_active": False}
        ).status_code
        == 403
    )
    assert (
        manager.patch(
            AGENCY + "/settings/operations", json={"timezone": "Europe/Paris"}
        ).status_code
        == 200
    )
    assert (
        manager.patch(
            AGENCY + "/settings/operations", json={"timezone": "UTC", "authentication": "off"}
        ).status_code
        == 422
    )
    assert manager.get(AGENCY + "/settings/operations").json()["data"]["timezone"] == "Europe/Paris"
    assert staff.get(AGENCY + "/members").status_code == 403
    assert staff.put(role(workspace, "new", "team_member")).status_code == 403


def test_single_use_invitation_and_revalidation(browser, workspace):
    manager, admin = browser("manager"), browser("admin")
    invite = manager.post(
        AGENCY + "/invitations", json={"email": "join@example.com", "role": "team_member"}
    )
    assert invite.status_code == 201
    token = invite.json()["data"]["token"]
    with Session(engine()) as db:
        assert db.scalars(select(AgencyInvitation.token_digest)).one() == digest(token)
    body = {"token": token, "full_name": "New hire", "password": secrets.token_urlsafe(24)}
    assert browser().post(REGISTER, json=body).status_code == 201
    assert browser().post(REGISTER, json=body).status_code == 400
    existing = manager.post(
        AGENCY + "/invitations", json={"email": "new@example.com", "role": "team_member"}
    ).json()["data"]
    assert browser().post(REGISTER, json={"token": existing["token"]}).status_code == 403
    assert admin.put(role(workspace, "new", "agency_manager")).status_code == 204
    assert browser("new").post(REGISTER, json={"token": existing["token"]}).status_code == 403
    assert (
        manager.post(
            AGENCY + "/invitations", json={"email": "admin@example.com", "role": "team_member"}
        ).status_code
        == 403
    )


def test_last_active_admin_and_concurrent_removal(browser, workspace):
    first = browser("admin")
    original = role(workspace, "admin", "admin")
    assert first.delete(original).status_code == 409
    assert first.patch(original, json={"is_active": False}).status_code == 409
    assert (
        first.patch(
            AGENCY + f"/members/{workspace['admin']}/account", json={"is_active": False}
        ).status_code
        == 409
    )
    second_role = role(workspace, "new", "admin")
    assert first.put(second_role).status_code == 204
    second = browser("new")
    barrier = Barrier(2)

    def remove(client, url):
        barrier.wait(timeout=15)
        return client.delete(url).status_code

    with ThreadPoolExecutor(2) as pool:
        jobs = [pool.submit(remove, first, second_role), pool.submit(remove, second, original)]
        assert sorted(job.result() for job in jobs) == [204, 403]
    with Session(engine()) as db:
        count = db.scalar(
            select(func.count())
            .select_from(AgencyMembership)
            .join(User)
            .where(AgencyMembership.role == "admin", AgencyMembership.is_active, User.is_active)
        )
        assert count == 1
        assert (
            db.scalar(
                select(func.count())
                .select_from(Audit)
                .where(Audit.action == "agency_membership.revoke")
            )
            == 1
        )


def test_competing_invitation_redemptions_create_one_identity(browser):
    manager = browser("manager")
    grant = manager.post(
        AGENCY + "/invitations", json={"email": "invited@example.com", "role": "team_member"}
    ).json()["data"]
    clients = [browser(), browser()]
    barrier = Barrier(2)
    body = {"token": grant["token"], "full_name": "Invitee", "password": secrets.token_urlsafe(24)}

    def accept(client):
        barrier.wait(timeout=15)
        return client.post(REGISTER, json=body).status_code

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(accept, clients)) == [201, 400]
    with Session(engine()) as db:
        uid = db.scalars(select(User.id).where(User.email == "invited@example.com")).one()
        assert (
            db.scalars(select(AgencyMembership.role).where(AgencyMembership.user_id == uid)).one()
            == "team_member"
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(Audit)
                .where(Audit.action == "agency_invitation.accepted")
            )
            == 1
        )
