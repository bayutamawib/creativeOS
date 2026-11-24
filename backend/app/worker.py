"""Run independent outbox and generation consumers in the existing worker service."""

import logging
import signal
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from threading import Event

from sqlalchemy.exc import SQLAlchemyError

from app.ai.runner import execute_one
from app.config import settings
from app.db import database_ready
from app.logging_config import configure_logging
from app.services.workflows import dispatch

Consumer = tuple[str, Callable[[], bool]]


def consumers(mode: str) -> tuple[Consumer, ...]:
    if mode == "all":
        return (("dispatcher", dispatch), ("generation", execute_one))
    if mode == "ai":
        return (("generation", execute_one),)
    if mode == "dispatch":
        return (("dispatcher", dispatch),)
    raise ValueError(f"Unsupported worker mode: {mode}")


def run() -> None:
    configure_logging()
    log = logging.getLogger("creativeos.worker")
    stop = Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    heartbeat = Path("/tmp/creativeos-worker-heartbeat")
    jobs: dict[str, Future[bool]] = {}
    active_consumers = consumers(settings().worker_mode)
    with ThreadPoolExecutor(max_workers=len(active_consumers)) as pool:
        while not stop.is_set():
            try:
                if database_ready():
                    heartbeat.touch()
                    for label, fn in active_consumers:
                        future = jobs.get(label)
                        if future is None or future.done():
                            if future and future.exception():
                                log.error("%s_iteration_failed", label)
                            jobs[label] = pool.submit(fn)
            except SQLAlchemyError:
                log.warning("database_unavailable")
            stop.wait(0.5)
    heartbeat.unlink(missing_ok=True)


if __name__ == "__main__":
    run()
