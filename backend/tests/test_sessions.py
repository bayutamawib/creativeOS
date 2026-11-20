from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import BrowserSession, User
from app.security import digest, now
from app.services.sessions import CSRF_COOKIE, SESSION_COOKIE

AUTH = "/api/v1/auth"


def test_session_cookie_rotation_and_revocation(browser, test_password):
    client = browser()
    login = client.post(
        AUTH + "/login", json={"email": "ADMIN@example.com", "password": test_password[0]}
    )
    assert login.status_code == 200
    session_header = next(
        h for h in login.headers.get_list("set-cookie") if h.startswith(SESSION_COOKIE)
    )
    assert all(
        attr.lower() in session_header.lower()
        for attr in ("HttpOnly", "Secure", "SameSite=lax", "Path=/")
    )
    token = client.cookies[SESSION_COOKIE]
    csrf = client.cookies[CSRF_COOKIE]
    with Session(engine()) as db:
        row = db.scalars(select(BrowserSession)).one()
        assert row.token_digest == digest(token)
        assert row.csrf_digest == digest(csrf)
        assert (
            db.scalars(select(User.password_hash).where(User.email == "admin@example.com"))
            .one()
            .startswith("$argon2id$")
        )
    assert client.get(AUTH + "/me").json()["data"]["agency_roles"] == ["admin"]
    assert client.post(AUTH + "/refresh").status_code == 403
    assert client.post(AUTH + "/logout", headers={"x-csrf-token": "incorrect"}).status_code == 403
    client.headers["x-csrf-token"] = csrf
    assert (
        client.post(AUTH + "/refresh", headers={"origin": "https://outside.example"}).status_code
        == 403
    )
    assert client.post(AUTH + "/refresh").status_code == 200
    assert client.cookies[SESSION_COOKIE] != token
    stale = browser()
    stale.cookies.set(SESSION_COOKIE, token)
    assert stale.get(AUTH + "/me").status_code == 401
    client.headers["x-csrf-token"] = client.cookies[CSRF_COOKIE]
    current_token = client.cookies[SESSION_COOKIE]
    assert client.post(AUTH + "/logout").status_code == 204
    stale.cookies.set(SESSION_COOKIE, current_token)
    assert stale.get(AUTH + "/me").status_code == 401


def test_denied_login_expiry_and_inactive_account(browser, workspace, test_password):
    anon = browser()
    assert anon.get(AUTH + "/me").status_code == 401
    for path in (
        "/agency/members",
        f"/clients/{workspace['north']}",
        f"/projects/{workspace['north-1']}/approval-delegations",
    ):
        assert anon.get("/api/v1" + path).status_code == 401
    body = {"email": "admin@example.com", "password": test_password[0]}
    assert (
        anon.post(
            AUTH + "/login", json=body, headers={"origin": "https://outside.example"}
        ).status_code
        == 403
    )
    assert anon.post(AUTH + "/login", json={**body, "password": "incorrect"}).status_code == 401
    client = browser("admin")
    with Session(engine()) as db, db.begin():
        db.scalars(select(BrowserSession)).one().expires_at = now() - timedelta(seconds=1)
    assert client.get(AUTH + "/me").status_code == 401
    fresh = browser("admin")
    with Session(engine()) as db, db.begin():
        db.get(User, workspace["admin"]).is_active = False
    assert fresh.get(AUTH + "/me").status_code == 401
    assert anon.post(AUTH + "/login", json=body).status_code == 401


def test_competing_session_renewals_issue_one_successor(browser):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    original = browser("admin")
    copies = [browser(), browser()]
    for client in copies:
        client.cookies.set(
            SESSION_COOKIE, original.cookies[SESSION_COOKIE], domain="testserver.local", path="/"
        )
        client.headers["x-csrf-token"] = original.cookies[CSRF_COOKIE]
    barrier = Barrier(2)

    def renew(client):
        barrier.wait(timeout=15)
        return client.post(AUTH + "/refresh").status_code

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(renew, copies)) == [200, 401]
    assert original.get(AUTH + "/me").status_code == 401
    assert sorted(client.get(AUTH + "/me").status_code for client in copies) == [200, 401]
