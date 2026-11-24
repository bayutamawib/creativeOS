import pytest

from app import worker


def test_worker_modes_select_only_the_intended_consumer(monkeypatch):
    def ai() -> bool:
        return True

    def outbox() -> bool:
        return True

    monkeypatch.setattr(worker, "execute_one", ai)
    monkeypatch.setattr(worker, "dispatch", outbox)

    assert worker.consumers("ai") == (("generation", ai),)
    assert worker.consumers("dispatch") == (("dispatcher", outbox),)
    assert worker.consumers("all") == (("dispatcher", outbox), ("generation", ai))


def test_worker_mode_rejects_unknown_consumer():
    with pytest.raises(ValueError, match="Unsupported worker mode"):
        worker.consumers("unexpected")
