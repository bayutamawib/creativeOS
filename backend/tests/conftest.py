import secrets
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from alembic import command
from app.config import settings
from app.db import engine
from app.main import app
from app.models import AgencyMembership, Client, ClientMembership, Project, User
from app.security import hash_password
from app.services.sessions import CSRF_COOKIE


@pytest.fixture(autouse=True)
def local_adapters(monkeypatch, tmp_path):
    monkeypatch.setenv("FILE_PROVIDER", "local")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("AI_PROVIDER", "fixture")
    monkeypatch.setenv("AI_MODEL", "fixture-v1")
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("DRIVE_ACCESS_TOKEN", raising=False)
    settings.cache_clear()
    yield
    settings.cache_clear()


@pytest.fixture(scope="session")
def test_password():
    raw = secrets.token_urlsafe(24)
    return raw, hash_password(raw)


@pytest.fixture
def workspace(monkeypatch, test_password):
    """Exercise the installed migrations and unmodified application against PostgreSQL."""
    original = engine()
    schema = "cp1_test_" + uuid4().hex
    with original.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA {schema}"))
    monkeypatch.setenv("PGOPTIONS", "-c search_path=" + schema)
    engine.cache_clear()
    test_engine = engine()
    try:
        command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")
        ids = {}
        with Session(test_engine) as db, db.begin():
            for name in ("admin", "manager", "staff", "new", "owner", "member", "foreign"):
                user = User(
                    email=name + "@example.com", full_name=name, password_hash=test_password[1]
                )
                db.add(user)
                db.flush()
                ids[name] = user.id
            for name, role in [
                ("admin", "admin"),
                ("manager", "agency_manager"),
                ("staff", "team_member"),
            ]:
                db.add(AgencyMembership(user_id=ids[name], role=role))
            for key in ("north", "south"):
                org = Client(company_name=key)
                db.add(org)
                db.flush()
                ids[key] = org.id
                for number in (1, 2):
                    project = Project(client_id=org.id, name=f"{key}-{number}")
                    db.add(project)
                    db.flush()
                    ids[project.name] = project.id
            for name, key, role in [
                ("owner", "north", "client_admin"),
                ("member", "north", "client_member"),
                ("foreign", "south", "client_admin"),
                ("staff", "south", "client_member"),
            ]:
                m = ClientMembership(user_id=ids[name], client_id=ids[key], role=role)
                db.add(m)
                db.flush()
                ids[name + "_membership"] = m.id
        yield ids
    finally:
        test_engine.dispose()
        engine.cache_clear()
        monkeypatch.delenv("PGOPTIONS")
        with original.begin() as connection:
            connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        original.dispose()


@pytest.fixture
def browser(workspace, test_password):
    clients = []

    def open_session(name=None):
        client = TestClient(
            app, base_url="https://testserver", headers={"origin": settings().web_origin}
        )
        clients.append(client)
        if name is not None:
            result = client.post(
                "/api/v1/auth/login",
                json={"email": name + "@example.com", "password": test_password[0]},
            )
            assert result.status_code == 200, result.text
            client.headers["x-csrf-token"] = client.cookies[CSRF_COOKIE]
        return client

    yield open_session
    for client in clients:
        client.close()
