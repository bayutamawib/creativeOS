from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_liveness():
    response = client.get("/health/live")
    assert response.json() == {"status": "alive"}
    assert response.headers["x-request-id"]


def test_database_and_migrations_ready():
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
