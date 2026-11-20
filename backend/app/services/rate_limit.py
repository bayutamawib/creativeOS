from datetime import timedelta

from fastapi import HTTPException, Request
from sqlalchemy import case, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import AuthRateLimit
from app.security import digest, now


def limit(db: Session, request: Request, action: str, subject: str) -> None:
    """Commit attempts independently so failed logins also consume the budget."""
    window = now().replace(second=0, microsecond=0)
    peer = request.client.host if request.client else "unknown"
    blocked = False
    with Session(db.get_bind()) as counter, counter.begin():
        counter.execute(
            delete(AuthRateLimit).where(AuthRateLimit.window_at < window - timedelta(minutes=1))
        )
        for label, value, maximum in (("peer", peer, 120), ("subject", subject, 12)):
            key = digest(action + "/" + label + "/" + value)
            stmt = insert(AuthRateLimit).values(key=key, window_at=window, attempts=1)
            attempts = counter.scalar(
                stmt.on_conflict_do_update(
                    index_elements=[AuthRateLimit.key],
                    set_={
                        "window_at": window,
                        "attempts": case(
                            (AuthRateLimit.window_at == window, AuthRateLimit.attempts + 1), else_=1
                        ),
                    },
                ).returning(AuthRateLimit.attempts)
            )
            if attempts and attempts > maximum:
                blocked = True
                break
    if blocked:
        raise HTTPException(429, "Too many attempts. Try again in a minute")
