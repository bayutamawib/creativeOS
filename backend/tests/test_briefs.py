from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from PIL import Image
from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.brief_models import FileAsset, Snapshot
from app.config import settings
from app.db import engine
from app.operations_models import Outbox
from app.services.assets import MAX_BYTES
from app.services.drive import DriveStorage

BASE = "/api/v1"


def upload(client, pid, name="guide.txt", body=b"Brand notes", mime="text/plain", **params):
    return client.post(
        BASE + "/files/upload",
        params={"project_id": str(pid), "file_name": name, **params},
        content=body,
        headers={"content-type": mime},
    )


def test_file_boundaries_and_validation(browser, workspace):
    owner, other, team, manager = [browser(n) for n in ("owner", "foreign", "staff", "manager")]
    pid = workspace["north-1"]
    assert upload(browser(), pid).status_code == 401
    assert upload(other, pid).status_code == 404
    assert upload(team, pid).status_code == 404
    for name, body, mime, status in [
        ("../guide.txt", b"x", "text/plain", 422),
        ("a.html", b"hello", "text/html", 415),
        ("a.png", b"not an image", "image/png", 415),
        ("large.txt", b"a" * (MAX_BYTES + 1), "text/plain", 413),
    ]:
        assert upload(owner, pid, name, body, mime).status_code == status
    result = upload(owner, pid)
    assert result.status_code == 201, result.text
    asset = result.json()["data"]["id"]
    path = BASE + "/files/" + asset
    assert owner.get(path + "/download").content == b"Brand notes"
    assert other.get(path).status_code == 404 and other.get(path + "/download").status_code == 404
    assert team.get(path + "/download").status_code == 404
    private = upload(manager, pid).json()["data"]["id"]
    assert owner.get(BASE + "/files/" + private + "/download").status_code == 404
    assert owner.get(BASE + "/files").json()["data"][0]["id"] == asset
    for project, identifier in [(workspace["north-2"], asset), (pid, private)]:
        resp = owner.post(
            f"{BASE}/projects/{project}/briefs",
            json={"title": "Brief", "objective": "Launch", "attachment_ids": [identifier]},
        )
        assert resp.status_code == 422
    assert manager.delete(path).status_code == 204
    assert owner.get(path + "/download").status_code == 404


def test_review_snapshots_and_atomic_approval(browser, workspace):
    manager, admin, owner, foreign = [browser(n) for n in ("manager", "admin", "owner", "foreign")]
    pid = workspace["north-1"]
    asset = upload(owner, pid).json()["data"]["id"]
    body = {"title": "Launch", "objective": "Awareness", "attachment_ids": [asset]}
    bid = owner.post(f"{BASE}/projects/{pid}/briefs", json=body).json()["data"]["id"]
    path = BASE + "/briefs/" + bid
    assert foreign.get(path).status_code == 404
    assert browser("member").post(path + "/submit", json={"expected_version": 1}).status_code == 403
    assert owner.post(path + "/approve", json={"expected_version": 1}).status_code == 403
    assert owner.post(path + "/submit", json={"expected_version": 1}).status_code == 200
    assert (
        owner.patch(path, json={"expected_version": 2, "title": "Silent edit"}).status_code == 409
    )
    assert manager.post(path + "/start-review", json={"expected_version": 2}).status_code == 200
    assert manager.post(path + "/request-revision", json={"expected_version": 3}).status_code == 422
    assert (
        manager.post(
            path + "/request-revision", json={"expected_version": 3, "feedback": "Clarify audience"}
        ).status_code
        == 200
    )
    assert (
        owner.patch(path, json={"expected_version": 4, "target_audience": "Designers"}).status_code
        == 200
    )
    assert owner.post(path + "/submit", json={"expected_version": 5}).status_code == 200
    assert (
        manager.put(
            f"{BASE}/clients/{workspace['north']}/brand-guidelines", json={"guidance": "Editorial"}
        ).status_code
        == 200
    )
    barrier = Barrier(2)

    def approve(client):
        barrier.wait()
        return client.post(path + "/approve", json={"expected_version": 6}).status_code

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(approve, [manager, admin])) == [200, 409]
    snapshot = owner.get(path).json()["data"]["snapshot_id"]
    assert (
        owner.patch(
            path, json={"expected_version": 7, "objective": "New goal", "attachment_ids": []}
        ).json()["data"]["status"]
        == "draft"
    )
    assert manager.delete(BASE + "/files/" + asset).status_code == 409
    assert foreign.get(path + "/snapshots").status_code == 404
    assert owner.get(path + "/snapshots").json()["data"][0]["fields"]["objective"] == "Awareness"
    with Session(engine()) as db:
        snap = db.get_one(Snapshot, UUID(snapshot))
        assert (
            snap.fields["objective"] == "Awareness"
            and snap.fields["target_audience"] == "Designers"
        )
        assert (
            snap.attachments[0]["id"] == asset
            and snap.brand["guidelines"]["guidance"] == "Editorial"
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(Outbox)
                .where(Outbox.event_type == "brief.approved")
            )
            == 1
        )
    with (
        pytest.raises(DBAPIError, match="Immutable creative record"),
        Session(engine()) as db,
        db.begin(),
    ):
        db.execute(update(Snapshot).where(Snapshot.id == UUID(snapshot)).values(version=99))


def test_drive_adapter_contract(monkeypatch):
    drive = DriveStorage()
    monkeypatch.delenv("DRIVE_ACCESS_TOKEN", raising=False)
    settings.cache_clear()
    with pytest.raises(HTTPException, match="credentials"):
        drive.put(uuid4(), b"raw", "text/plain")
    with pytest.raises(HTTPException, match="reference"):
        drive.read("../private")
    calls = []

    def transport(path, method, data=None, mime=""):
        calls.append((path, method, data, mime))
        return b'{"id":"private_object_id"}' if method == "POST" else b"raw"

    monkeypatch.setattr(drive, "_call", transport)
    ref = drive.put(uuid4(), b"raw", "text/plain")
    assert (
        ref == "private_object_id" and b"raw" in calls[0][2] and "multipart/related" in calls[0][3]
    )
    assert drive.read(ref) == b"raw" and calls[-1][:2] == (
        "drive/v3/files/private_object_id?alt=media",
        "GET",
    )
    drive.discard(ref)
    assert calls[-1][:2] == ("drive/v3/files/private_object_id", "DELETE")


def test_image_sanitization_and_legacy_storage(browser, workspace):
    owner = browser("owner")
    stream = BytesIO()
    Image.new("RGB", (2, 2), color="blue").save(stream, format="PNG")
    raw = stream.getvalue() + b"trailing metadata"
    assert (
        upload(owner, workspace["north-1"], "reference.jpg", raw, "image/jpeg").status_code == 415
    )
    f = upload(owner, workspace["north-1"], "reference.png", raw, "image/png").json()["data"]
    url = BASE + "/files/" + f["id"] + "/download"
    with Session(engine()) as db, db.begin():
        db.get_one(FileAsset, UUID(f["id"])).provider_ref = None
    received = owner.get(url)
    assert received.status_code == 200 and b"trailing metadata" not in received.content
    assert Image.open(BytesIO(received.content)).size == (2, 2)
    (Path(settings().storage_dir) / UUID(f["id"]).hex).write_bytes(b"changed")
    assert owner.get(url).status_code == 503
