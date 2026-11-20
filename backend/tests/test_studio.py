import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO
from threading import Barrier
from urllib.error import HTTPError
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import providers, runner
from app.ai.contracts import GenerationFailure, validate
from app.ai.providers import Compatible, Fixture, Response
from app.ai.reporting import VerifiedMetrics, summarize
from app.ai_models import ContentItem, ContentRevision, Generation, Proposal
from app.config import settings
from app.db import engine
from app.operations_models import Outbox
from app.project_models import Task
from app.security import now
from app.services import workflows

B = "/api/v1"


def approved(owner, manager, pid):
    brief = owner.post(
        f"{B}/projects/{pid}/briefs",
        json={
            "title": "Editorial",
            "objective": "Introduce the collection",
            "preferred_channels": ["Instagram"],
            "requested_item_count": 2,
        },
    ).json()["data"]
    path = B + "/briefs/" + brief["id"]
    assert owner.post(path + "/submit", json={"expected_version": 1}).status_code == 200
    snap = manager.post(path + "/approve", json={"expected_version": 2}).json()["data"][
        "snapshot_id"
    ]
    return path, snap


def request(client, path, action="analyze", data=None, key=None):
    return client.post(
        path + "/" + action, json=data or {}, headers={"Idempotency-Key": key or str(uuid4())}
    )


def poll(client, job):
    return client.get(B + "/ai-generations/" + str(job)).json()["data"]


def test_generation_scope_keys_and_staleness(browser, workspace):
    manager, owner, staff = [browser(n) for n in ("manager", "owner", "staff")]
    path, snapshot = approved(owner, manager, workspace["north-1"])
    assert request(owner, path).status_code == 403
    assert request(staff, path).status_code == 404
    assert request(manager, path, "generate-creative-direction").status_code == 409
    assert request(manager, path, "generate-content-plan").status_code == 409
    barrier = Barrier(2)

    def enqueue(client):
        barrier.wait()
        return request(client, path, key="analysis").json()["data"]["generation_id"]

    with ThreadPoolExecutor(2) as pool:
        a, b = pool.map(enqueue, [manager, browser("manager")])
    assert a == b
    assert request(manager, path, key="analysis", data={"snapshot_id": snapshot}).status_code == 409
    assert owner.get(B + "/ai-generations/" + a).status_code == 403
    assert staff.get(B + "/ai-generations/" + a).status_code == 404
    assert browser("foreign").get(path + "/studio").status_code in {403, 404}
    assert owner.patch(path, json={"expected_version": 3, "objective": "New"}).status_code == 200
    assert not runner.execute_one()
    assert poll(manager, a)["status"] == "cancelled"
    assert request(manager, path, data={"snapshot_id": snapshot}).status_code == 409


def test_human_gates_copy_and_idempotent_business_writes(browser, workspace):
    manager, owner = browser("manager"), browser("owner")
    pid = workspace["north-1"]
    path, snap = approved(owner, manager, pid)
    for action in ("analyze", "generate-creative-direction"):
        queued = request(manager, path, action)
        assert queued.status_code == 202
        assert runner.execute_one()
        assert poll(manager, queued.json()["data"]["generation_id"])["status"] == "completed"
    proposals = manager.get(path + "/proposals").json()["data"]
    direction = proposals[0]["id"]
    select_path = B + "/proposals/" + direction + "/approve"
    opts = {"direction_proposal_id": direction, "snapshot_id": snap, "target_count": 2}
    assert request(manager, path, "generate-content-plan", opts).status_code == 409
    assert owner.post(select_path).status_code == 403
    assert manager.post(select_path).status_code == 200
    assert manager.post(select_path).status_code == 200
    assert manager.post(B + "/proposals/" + proposals[1]["id"] + "/approve").status_code == 409
    assert (
        manager.post(B + "/proposals/" + proposals[1]["id"] + "/reject").json()["data"]["decision"]
        == "rejected"
    )
    j = request(manager, path, "generate-content-plan", opts).json()["data"]["generation_id"]
    assert runner.execute_one()
    assert len(poll(manager, j)["output"]["content_plan"]) == 2
    item = next(
        p for p in manager.get(path + "/proposals").json()["data"] if p["kind"] == "plan_item"
    )["id"]
    create = f"{B}/projects/{pid}/content-items"
    assert manager.post(create, json={"proposal_id": item}).status_code == 409
    barrier = Barrier(2)

    def choose(client):
        barrier.wait()
        return client.post(B + "/proposals/" + item + "/approve").status_code

    with ThreadPoolExecutor(2) as pool:
        assert list(pool.map(choose, [manager, browser("admin")])) == [200, 200]
    d = manager.post(create, json={"proposal_id": item}).json()["data"]
    assert d == manager.post(create, json={"proposal_id": item}).json()["data"]
    draft = B + "/content-items/" + d["id"]
    assert owner.get(draft).status_code == 403
    copies = []
    for _i in range(2):
        gen = request(
            manager,
            draft,
            "generate",
            {"revision_id": d["current_revision_id"], "feedback": "Use editorial language"},
        )
        assert runner.execute_one()
        copies.append(gen.json()["data"]["generation_id"])

    def save(key):
        return manager.post(draft + "/revisions", json={"generation_id": key})

    assert save(copies[0]).json()["data"]["revision_number"] == 2
    assert save(copies[0]).json()["data"]["revision_number"] == 2
    assert save(copies[1]).status_code == 409
    with Session(engine()) as db:
        for model, count in [(ContentItem, 1), (ContentRevision, 2), (Task, 2)]:
            assert db.scalar(select(func.count()).select_from(model)) == count
        job = db.get_one(Generation, UUID(j))
        assert job.input_snapshot["direction"] == db.get_one(Proposal, UUID(direction)).payload
        assert (
            job.requested_by == workspace["manager"]
            and job.prompt_version
            and job.provider == "fixture"
        )


class BadProvider:
    def generate(self, *args):
        return Response('{"content_plan":"unvalidated"}')


def due(job):
    with Session(engine()) as db, db.begin():
        db.get_one(Generation, UUID(job)).next_attempt_at = now() - timedelta(seconds=1)


def test_failure_retries_and_restart(browser, workspace):
    manager = browser("manager")
    path, _ = approved(browser("owner"), manager, workspace["north-1"])
    key = request(manager, path).json()["data"]["generation_id"]
    assert runner.execute_one(BadProvider())
    assert poll(manager, key)["status"] == "pending"
    due(key)
    assert runner.execute_one(BadProvider())
    result = poll(manager, key)
    assert (
        result["status"] == "failed"
        and result["error_code"] == "invalid_output"
        and result["output"] is None
    )
    key = request(manager, path).json()["data"]["generation_id"]
    with Session(engine(), expire_on_commit=False) as db, db.begin():
        job, token = runner.claim(db)
    with Session(engine()) as db, db.begin():
        assert runner.claim(db) is None
        db.get_one(Generation, job.id).claim_expires_at = now() - timedelta(seconds=1)
    assert runner.execute_one()
    assert poll(manager, key)["attempt"] == 2 and poll(manager, key)["status"] == "completed"


def test_worker_revalidates_assignment(browser, workspace):
    manager, staff = browser("manager"), browser("staff")
    pid = workspace["north-1"]
    path, _ = approved(browser("owner"), manager, pid)
    member = f"{B}/projects/{pid}/members"
    assert manager.post(member, json={"user_id": str(workspace["staff"])}).status_code == 204
    key = request(staff, path).json()["data"]["generation_id"]
    assert manager.delete(member + "/" + str(workspace["staff"])).status_code == 204
    assert not runner.execute_one()
    assert (
        poll(manager, key)["status"] == "cancelled"
        and staff.get(B + "/ai-generations/" + key).status_code == 404
    )


def test_provider_contracts_and_configuration(monkeypatch):
    monkeypatch.delenv("AI_API_KEY", raising=False)
    settings.cache_clear()
    with pytest.raises(GenerationFailure, match="missing_credentials"):
        Compatible().generate("brief_analysis", "test", {}, {})
    for bad in ["{}", "invalid", '{"content_plan":[]}']:
        with pytest.raises(GenerationFailure, match="invalid_output"):
            validate("content_plan", bad, {"target_count": 1, "channels": ["Instagram"]})
    result = summarize(
        VerifiedMetrics(period="November", completed_tasks=4, open_tasks=2, overdue_tasks=0)
    )
    assert result.completed_work == ["Completed tasks: 4"]
    context = {
        "brief": {"title": "Brief", "objective": "Educate", "target_audience": "Designers"},
        "direction": {"key_message": "Read", "visual_direction": "Editorial"},
    }
    params = {"channels": ["Website"], "target_count": 1}
    raw = Fixture().generate("content_plan", "fixture-v1", context, params).content
    with pytest.raises(GenerationFailure, match="invalid_plan"):
        validate("content_plan", raw, params | {"target_count": 2})
    with pytest.raises(GenerationFailure, match="invalid_plan"):
        validate("content_plan", raw, params | {"channels": ["TikTok"]})


def test_provider_failure_budget_and_late_worker(browser, workspace):
    manager = browser("manager")
    path, _ = approved(browser("owner"), manager, workspace["north-1"])
    key = request(manager, path).json()["data"]["generation_id"]

    class Timeout:
        def generate(self, *args):
            raise GenerationFailure("provider_unavailable", True)

    for attempt in range(1, 4):
        assert runner.execute_one(Timeout())
        status = poll(manager, key)
        assert status["attempt"] == attempt and status["error_code"] == "provider_unavailable"
        assert status["status"] == ("failed" if attempt == 3 else "pending")
        due(key)
    assert not runner.execute_one()
    key = request(manager, path).json()["data"]["generation_id"]

    class Late:
        def generate(self, *args):
            with Session(engine()) as db, db.begin():
                db.get_one(Generation, UUID(key)).claim_expires_at = now() - timedelta(seconds=1)
            assert runner.execute_one(Fixture())
            raise GenerationFailure("provider_unavailable", True)

    assert runner.execute_one(Late())
    assert poll(manager, key)["attempt"] == 2 and poll(manager, key)["status"] == "completed"


def test_workflow_event_authorization_and_replay(browser, workspace):
    guest, manager, owner = browser(), browser("manager"), browser("owner")
    path, _ = approved(owner, manager, workspace["north-1"])
    manual = request(manager, path).json()["data"]["generation_id"]
    prefix = B + "/internal/workflow-runs"
    headers = {"X-Creative-Service": workflows.secret(settings().workflow_key)}

    def start(raw, execution):
        stamp = str(int(time.time()))
        return guest.post(
            prefix,
            json={
                "raw": raw,
                "timestamp": stamp,
                "signature": workflows.signature(stamp + "." + raw),
                "execution_id": execution,
                "workflow": "WF-B",
            },
            headers=headers,
        ).json()["run_id"]

    with Session(engine()) as db, db.begin():
        event, token, _, raw = workflows.claim(db)
    first = start(raw, "1")
    url = prefix + "/" + first + "/generations"
    assert guest.post(url, json={"stage": "brief_analysis"}).status_code == 403
    assert guest.post(url, json={"stage": "content_plan"}, headers=headers).status_code == 403
    assert guest.get(url + "/" + manual, headers=headers).status_code == 404
    job = guest.post(url, json={"stage": "brief_analysis"}, headers=headers).json()["generation_id"]
    with Session(engine()) as db, db.begin():
        workflows.settle(db, event, token, None)
        db.get_one(Outbox, event).next_attempt_at = now()
    with Session(engine()) as db, db.begin():
        _, _, _, raw = workflows.claim(db)
    second = start(raw, "2")
    assert first != second
    assert guest.post(url, json={"stage": "brief_analysis"}, headers=headers).status_code == 409
    assert (
        guest.post(
            prefix + "/" + second + "/generations",
            json={"stage": "brief_analysis"},
            headers=headers,
        ).json()["generation_id"]
        == job
    )
    assert (
        guest.post(
            prefix + "/" + second + "/outcome", json={"status": "completed"}, headers=headers
        ).status_code
        == 409
    )


def test_compatible_provider_transport(monkeypatch):
    monkeypatch.setenv("AI_ENDPOINT", "https://provider.invalid/chat/completions")
    monkeypatch.setenv("AI_API_KEY", str(uuid4()))
    settings.cache_clear()
    transport_error = None

    class Transport:
        def open(self, req, *, timeout):
            payload = json.loads(req.data)
            assert timeout == settings().ai_timeout_seconds
            assert payload["model"] == "test-model" and payload["response_format"] == {
                "type": "json_object"
            }
            assert payload["messages"][0]["role"] == "system"
            if transport_error:
                raise transport_error
            return BytesIO(
                json.dumps(
                    {
                        "choices": [{"message": {"content": "{}"}}],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 2},
                    }
                ).encode()
            )

    monkeypatch.setattr(providers, "build_opener", lambda *_: Transport())

    def generate():
        return Compatible().generate(
            "brief_analysis", "test-model", {}, {"temperature": 0.2, "max_output_tokens": 1000}
        )

    assert generate() == Response("{}", 10, 2)
    for err, code, retry in [
        (TimeoutError(), "provider_unavailable", True),
        (
            HTTPError("https://provider.invalid", 429, "rate limit", None, None),
            "provider_rate_limit",
            True,
        ),
        (
            HTTPError("https://provider.invalid", 401, "unauthorized", None, None),
            "provider_http_error",
            False,
        ),
    ]:
        transport_error = err
        with pytest.raises(GenerationFailure) as failure:
            generate()
        assert failure.value.code == code and failure.value.retryable == retry


def test_unconfigured_live_job_records_terminal_error(browser, workspace, monkeypatch):
    manager = browser("manager")
    path, _ = approved(browser("owner"), manager, workspace["north-1"])
    monkeypatch.setenv("AI_PROVIDER", "compatible")
    monkeypatch.setenv("AI_MODEL", "test-model")
    settings.cache_clear()
    key = request(manager, path).json()["data"]["generation_id"]
    assert runner.execute_one()
    job = poll(manager, key)
    assert (
        job["status"] == "failed"
        and job["attempt"] == 1
        and job["error_code"] == "missing_credentials"
    )
    assert job["output"] is None and not runner.execute_one()
