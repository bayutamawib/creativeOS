from io import BytesIO

from PIL import Image
from sqlalchemy.orm import Session
from test_reviews import build_draft

from app.config import settings
from app.db import engine
from app.models import ClientMembership

BASE = "/api/v1"


def image_upload(client, project, name="cover.png", visibility="internal"):
    buffer = BytesIO()
    Image.new("RGB", (900, 600), "#4f46e5").save(buffer, format="PNG")
    response = client.post(
        BASE + "/files/upload",
        params={
            "project_id": str(project),
            "file_name": name,
            "visibility": visibility,
            "category": "creative_asset",
        },
        content=buffer.getvalue(),
        headers={"Content-Type": "image/png"},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def sample_mp4():
    def box(kind, payload):
        return (len(payload) + 8).to_bytes(4, "big") + kind + payload

    return box(b"ftyp", b"isom\0\0\0\0isom") + box(b"moov", b"metadata") + box(b"mdat", b"sample video bytes")


def video_upload(client, project, name="clip.mp4", visibility="internal", body=None):
    response = client.post(
        BASE + "/files/upload",
        params={"project_id": str(project), "file_name": name, "visibility": visibility, "category": "creative_asset"},
        content=sample_mp4() if body is None else body,
        headers={"Content-Type": "video/mp4"},
    )
    return response


def test_video_cover_range_and_access(browser, workspace, monkeypatch):
    manager, owner, foreign, staff = [browser(n) for n in ("manager", "owner", "foreign", "staff")]
    pid = workspace["north-1"]
    assert video_upload(manager, pid, body=b"not an mp4").status_code == 415
    monkeypatch.setenv("VIDEO_MAX_BYTES", str(1024 * 1024))
    settings.cache_clear()
    oversized = sample_mp4() + b"x" * (1024 * 1024)
    assert video_upload(manager, pid, body=oversized).status_code == 413
    monkeypatch.delenv("VIDEO_MAX_BYTES")
    settings.cache_clear()
    video = video_upload(manager, pid).json()["data"]["id"]
    cover = image_upload(manager, pid, "poster.png")
    other = image_upload(manager, workspace["south-1"], "other.png")
    path = f"{BASE}/files/{video}/stream"
    for reader in (browser(), owner, foreign, staff):
        assert reader.get(path, headers={"Range": "bytes=0-3"}).status_code in (401, 404)
    assert manager.put(f"{BASE}/files/{video}/cover", json={"cover_file_id": other}).status_code in (404, 422)
    assert manager.put(f"{BASE}/files/{video}/cover", json={"cover_file_id": cover}).status_code == 200
    assert manager.get(f"{BASE}/files/{video}").json()["data"]["cover_file_id"] == cover
    project = next(p for p in manager.get(BASE + "/projects?portal=agency").json()["data"] if p["id"] == str(pid))
    assert project["cover_video_id"] == video and project["cover_file_id"] == cover
    uncovered = video_upload(manager, pid, name="uncovered.mp4").json()["data"]["id"]
    project = next(p for p in manager.get(BASE + "/projects?portal=agency").json()["data"] if p["id"] == str(pid))
    assert project["cover_video_id"] == uncovered and project["cover_file_id"] is None
    full = manager.get(path)
    assert full.status_code == 200 and full.content == sample_mp4()
    assert full.headers["accept-ranges"] == "bytes"
    assert full.headers["cache-control"] == "private, no-store"
    for requested, expected in (("bytes=0-3", sample_mp4()[:4]), ("bytes=5-", sample_mp4()[5:]), ("bytes=-4", sample_mp4()[-4:])):
        res = manager.get(path, headers={"Range": requested})
        assert res.status_code == 206 and res.content == expected
        assert res.headers["content-length"] == str(len(expected))
        assert res.headers["content-range"].endswith(f"/{len(sample_mp4())}")
    invalid = manager.get(path, headers={"Range": "bytes=999-"})
    assert invalid.status_code == 416 and invalid.headers["content-range"] == f"bytes */{len(sample_mp4())}"
    assert manager.get(path, headers={"Range": "bytes=0-3,5-8"}).status_code == 416
    assert manager.head(path, headers={"Range": "bytes=0-3"}).status_code == 206
    assert manager.get(f"{BASE}/files/{cover}/stream").status_code == 415
    assert manager.delete(f"{BASE}/files/{video}").status_code == 204
    assert manager.get(path, headers={"Range": "bytes=0-3"}).status_code == 404


def test_video_release_freezes_cover_and_client_decision(browser, workspace):
    url, rev = build_draft(browser, workspace)
    manager, owner, foreign = browser("manager"), browser("owner"), browser("foreign")
    pid = workspace["north-1"]
    video = video_upload(manager, pid).json()["data"]["id"]
    cover = image_upload(manager, pid, "video-cover.png")
    assert manager.put(f"{BASE}/files/{video}/cover", json={"cover_file_id": cover}).status_code == 200
    saved = manager.post(url + "/revisions", json={**rev, "headline": "Video", "caption": "Review video", "attachment_ids": [video]})
    assert saved.status_code == 201
    rev = {"revision_id": manager.get(url).json()["data"]["current_revision_id"]}
    assert manager.put(f"{BASE}/files/{video}/cover", json={"cover_file_id": cover}).status_code == 409
    assert owner.get(f"{BASE}/files/{video}/stream", headers={"Range": "bytes=0-3"}).status_code == 404
    assert owner.get(f"{BASE}/files/{video}/download?portal=client").status_code == 404
    assert owner.get(f"{BASE}/files/{cover}?portal=client").status_code == 404
    manager.post(url + "/submit-for-internal-review", json=rev)
    assert manager.post(url + "/approve-and-release", json=rev).status_code == 200
    assert owner.get(f"{BASE}/files/{video}/stream?portal=client", headers={"Range": "bytes=0-3"}).status_code == 404
    assert owner.get(f"{BASE}/files/{video}/download?portal=client").status_code == 404
    assert owner.get(f"{BASE}/files/{cover}/thumbnail?portal=client").status_code == 404
    assert foreign.get(f"{BASE}/files/{video}/stream").status_code == 404
    item = owner.get(f"{BASE}/approvals?portal=client&project_id={pid}").json()["data"][0]
    assert item["history"][0]["files"] == []
    assert owner.post(url + "/client-approval", json=rev).status_code == 200
    with Session(engine()) as db, db.begin():
        db.get_one(ClientMembership, workspace["owner_membership"]).is_active = False
    assert owner.get(f"{BASE}/files/{video}/stream?portal=client", headers={"Range": "bytes=0-3"}).status_code == 404


def test_media_authorization_covers_and_no_shared_cache(browser, workspace):
    manager, owner, foreign, staff = [browser(n) for n in ("manager", "owner", "foreign", "staff")]
    pid = workspace["north-1"]
    private = image_upload(manager, pid)
    shared = image_upload(owner, pid, "shared.png", "client_visible")
    other = image_upload(manager, workspace["south-1"])
    for suffix in ("", "/download", "/thumbnail", "/preview"):
        path = f"{BASE}/files/{private}{suffix}"
        assert browser().get(path).status_code == 401
        assert owner.get(path + "?portal=client").status_code == 404
        assert foreign.get(path + "?portal=client").status_code == 404
        assert manager.get(path).status_code == 200
    for kind in ("thumbnail", "preview"):
        path = f"{BASE}/files/{private}/{kind}"
        assert staff.get(path + "?portal=agency").status_code == 404
        res = owner.get(f"{BASE}/files/{shared}/{kind}?portal=client")
        assert res.status_code == 200
        assert res.headers["cache-control"] == "private, no-store"
        assert res.headers["vary"] == "Cookie"
        assert res.headers["x-content-type-options"] == "nosniff"
        assert res.headers["content-disposition"] == "inline"
        assert Image.open(BytesIO(res.content)).size == (
            (640, 427) if kind == "thumbnail" else (900, 600)
        )
    assert owner.get(f"{BASE}/files/{shared}/download?portal=client").status_code == 200
    listing = owner.get(f"{BASE}/files?project_id={pid}&portal=client").json()["data"]
    assert shared in [row["id"] for row in listing] and private not in [row["id"] for row in listing]
    rows = owner.get(BASE + "/projects?portal=client").json()["data"]
    assert next(p for p in rows if p["id"] == str(pid))["cover_file_id"] == shared
    assert all(p["cover_file_id"] != other for p in rows)
    fallback = next(p for p in rows if p["id"] == str(workspace["north-2"]))
    assert fallback["cover_file_id"] is None
    text = manager.post(
        BASE + "/files/upload",
        params={"project_id": str(pid), "file_name": "notes.txt"},
        content=b"Notes",
        headers={"Content-Type": "text/plain"},
    ).json()["data"]["id"]
    assert manager.get(f"{BASE}/files/{text}/preview").status_code == 415
    assert manager.delete(f"{BASE}/files/{shared}").status_code == 204
    assert owner.get(f"{BASE}/files/{shared}/thumbnail").status_code == 404


def test_exact_revision_images_and_membership_revocation(browser, workspace):
    url, rev = build_draft(browser, workspace)
    manager, owner, foreign = browser("manager"), browser("owner"), browser("foreign")
    pid = workspace["north-1"]
    released = image_upload(manager, pid, "released.png")
    draft = image_upload(manager, pid, "unreleased.png")

    def save(file):
        nonlocal rev
        assert (
            manager.post(
                url + "/revisions",
                json={**rev, "headline": "Image", "caption": "Caption", "attachment_ids": [file]},
            ).status_code
            == 201
        )
        rev = {"revision_id": manager.get(url).json()["data"]["current_revision_id"]}

    save(released)
    assert owner.get(f"{BASE}/files/{released}/thumbnail").status_code == 404
    manager.post(url + "/submit-for-internal-review", json=rev)
    assert manager.post(url + "/approve-and-release", json=rev).status_code == 200
    save(draft)
    rows = owner.get(f"{BASE}/approvals?portal=client&project_id={pid}").json()["data"]
    item = next(i for i in rows if i["id"] == url.split("/")[-1])
    assert len(item["history"]) == 1
    assert item["history"][0]["files"] == []
    assert owner.get(f"{BASE}/files/{released}/preview").status_code == 404
    assert owner.get(f"{BASE}/files/{draft}/thumbnail").status_code == 404
    assert foreign.get(f"{BASE}/files/{released}/preview").status_code == 404
    listing = owner.get(f"{BASE}/files?project_id={pid}&portal=client").json()["data"]
    assert released not in [f["id"] for f in listing] and draft not in [f["id"] for f in listing]
    with Session(engine()) as db, db.begin():
        db.get_one(ClientMembership, workspace["owner_membership"]).is_active = False
    assert owner.get(f"{BASE}/files/{released}/preview").status_code == 404
    assert owner.get(BASE + "/projects?portal=client").json()["data"] == []
