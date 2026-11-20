import json
import secrets
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import engine
from app.models import PasswordReset
from app.security import digest


def test_private_local_delivery_and_single_use_reset(browser, monkeypatch, tmp_path):
    monkeypatch.setattr(settings(), "app_env", "development")
    monkeypatch.setattr(settings(), "dev_mail_dir", str(tmp_path))
    existing = browser("member")
    visitor = browser()
    url = "/api/v1/auth/forgot-password"
    unknown = visitor.post(url, json={"email": "unknown@example.com"})
    result = visitor.post(url, json={"email": "member@example.com"})
    assert result.status_code == unknown.status_code == 202
    assert result.json() == unknown.json()
    (msg,) = tmp_path.iterdir()
    assert msg.stat().st_mode & 0o077 == 0
    token = urlsplit(json.loads(msg.read_text())["reset_url"]).fragment
    with Session(engine()) as db:
        assert db.scalars(select(PasswordReset.token_digest)).one() == digest(token)
    password = secrets.token_urlsafe(24)
    payload = {"token": token, "password": password}
    assert visitor.post("/api/v1/auth/reset-password", json=payload).status_code == 204
    assert visitor.post("/api/v1/auth/reset-password", json=payload).status_code == 400
    assert existing.get("/api/v1/auth/me").status_code == 401
    assert (
        visitor.post(
            "/api/v1/auth/login", json={"email": "member@example.com", "password": password}
        ).status_code
        == 200
    )


def test_public_auth_limits_survive_rolled_back_requests(browser, monkeypatch):
    from app.services import rate_limit

    timestamp = rate_limit.now()
    monkeypatch.setattr(rate_limit, "now", lambda: timestamp)
    client = browser()
    for _ in range(12):
        assert (
            client.post("/api/v1/auth/register", json={"token": "absent-token-" * 4}).status_code
            == 400
        )
    assert (
        client.post("/api/v1/auth/register", json={"token": "absent-token-" * 4}).status_code == 429
    )
