"""Dispatch committed events with expiring PostgreSQL claims."""

import logging
import signal
from pathlib import Path
from threading import Event

from sqlalchemy.exc import SQLAlchemyError

from app.db import database_ready
from app.logging_config import configure_logging
from app.services.workflows import dispatch


def run() -> None:
    configure_logging()
    logger = logging.getLogger("creativeos.worker")
    stop = Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    heartbeat = Path("/tmp/creativeos-worker-heartbeat")
    logger.info("worker_started")
    while not stop.is_set():
        try:
            if database_ready():
                heartbeat.touch()
                if dispatch():
                    continue
        except SQLAlchemyError:
            logger.warning("database_unavailable")
        stop.wait(1)
    heartbeat.unlink(missing_ok=True)


if __name__ == "__main__":
    run()
