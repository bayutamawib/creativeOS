"""Run independent outbox and generation consumers in the existing worker service."""

import logging
import signal
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from threading import Event

from sqlalchemy.exc import SQLAlchemyError

from app.ai.runner import execute_one
from app.db import database_ready
from app.logging_config import configure_logging
from app.services.workflows import dispatch


def run() -> None:
    configure_logging()
    log = logging.getLogger("creativeos.worker")
    stop = Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    heartbeat = Path("/tmp/creativeos-worker-heartbeat")
    jobs: dict[str, Future[bool]] = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        while not stop.is_set():
            try:
                if database_ready():
                    heartbeat.touch()
                    for label, fn in (("dispatcher", dispatch), ("generation", execute_one)):
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
