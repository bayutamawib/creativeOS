import json
import os
import secrets
from datetime import timedelta
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.models import BrowserSession, PasswordReset, User
from app.security import digest, hash_password, now


def request_reset(db: Session, email: str) -> None:
    if settings().app_env != "development":
        raise HTTPException(503, "Password recovery delivery unavailable")
    user = db.scalar(
        select(User).where(User.email == email.lower(), User.is_active).with_for_update()
    )
    if not user:
        return
    token = secrets.token_urlsafe(40)
    db.execute(
        update(PasswordReset)
        .where(PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None))
        .values(used_at=now())
    )
    reset = PasswordReset(
        user_id=user.id, token_digest=digest(token), expires_at=now() + timedelta(minutes=20)
    )
    db.add(reset)
    db.flush()
    # Local delivery adapter. Transaction rollback makes any undelivered or orphaned token unusable.
    inbox = Path(settings().dev_mail_dir)
    inbox.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(inbox / f"{reset.id}.json", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as message:
        json.dump(
            {
                "to": user.email,
                "mode": "development",
                "reset_url": settings().web_origin + "/reset-password#" + token,
            },
            message,
        )


def reset_password(db: Session, token: str, password: str) -> None:
    token_hash = digest(token)
    user_id = db.scalar(
        select(PasswordReset.user_id).where(PasswordReset.token_digest == token_hash)
    )
    user = (
        db.scalar(select(User).where(User.id == user_id, User.is_active).with_for_update())
        if user_id
        else None
    )
    row = db.scalar(
        select(PasswordReset).where(PasswordReset.token_digest == token_hash).with_for_update()
    )
    if not user or not row or row.used_at or row.expires_at <= now():
        raise HTTPException(400, "Reset link unavailable")
    row.used_at = now()
    user.password_hash = hash_password(password)
    db.execute(
        update(BrowserSession)
        .where(BrowserSession.user_id == user.id, BrowserSession.revoked_at.is_(None))
        .values(revoked_at=now())
    )
