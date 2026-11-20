import secrets
from datetime import timedelta
from typing import Any

from fastapi import HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AgencyMembership, BrowserSession, Client, ClientMembership, User
from app.schemas import Login
from app.security import digest, now, password_matches

SESSION_COOKIE = "__Host-creative_session"
CSRF_COOKIE = "__Host-creative_csrf"


def same_origin(request: Request) -> None:
    if request.headers.get("origin") != settings().web_origin:
        raise HTTPException(403, "Invalid request origin")


def current(db: Session, request: Request, *, lock: bool = False) -> BrowserSession:
    token = request.cookies.get(SESSION_COOKIE, "")
    stmt = (
        select(BrowserSession)
        .join(User)
        .where(
            BrowserSession.token_digest == digest(token),
            BrowserSession.revoked_at.is_(None),
            BrowserSession.expires_at > now(),
            BrowserSession.absolute_expires_at > now(),
            User.is_active,
        )
    )
    if lock:
        stmt = stmt.with_for_update(of=BrowserSession)
    session = db.scalar(stmt)
    if session is None:
        raise HTTPException(401, "Sign in required")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        same_origin(request)
        supplied = request.headers.get("x-csrf-token", "")
        if not secrets.compare_digest(session.csrf_digest, digest(supplied)):
            raise HTTPException(403, "Invalid CSRF token")
    return session


def describe(db: Session, user: User) -> dict[str, Any]:
    roles = db.scalars(
        select(AgencyMembership.role)
        .where(
            AgencyMembership.user_id == user.id,
            AgencyMembership.is_active,
        )
        .order_by(AgencyMembership.role)
    ).all()
    memberships = db.execute(
        select(ClientMembership, Client.company_name)
        .join(Client)
        .where(
            ClientMembership.user_id == user.id,
            ClientMembership.is_active,
        )
        .order_by(Client.company_name)
    ).all()
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "agency_roles": roles,
        "client_memberships": [
            {"id": m.id, "client_id": m.client_id, "role": m.role, "company_name": name}
            for m, name in memberships
        ],
    }


def rotate(session: BrowserSession, response: Response) -> None:
    token, csrf = secrets.token_urlsafe(40), secrets.token_urlsafe(32)
    session.token_digest, session.csrf_digest = digest(token), digest(csrf)
    timestamp = now()
    session.expires_at = min(timestamp + timedelta(minutes=30), session.absolute_expires_at)
    ttl = int((session.expires_at - timestamp).total_seconds())
    for name, value, http_only in [(SESSION_COOKIE, token, True), (CSRF_COOKIE, csrf, False)]:
        response.set_cookie(
            name, value, secure=True, httponly=http_only, samesite="lax", path="/", max_age=ttl
        )


def login(db: Session, payload: Login, response: Response) -> dict[str, Any]:
    user = db.scalar(select(User).where(User.email == str(payload.email).lower()).with_for_update())
    if (
        not password_matches(
            user.password_hash if user else None, payload.password.get_secret_value()
        )
        or not user
        or not user.is_active
    ):
        raise HTTPException(401, "Invalid credentials")
    user.last_login_at = now()
    session = BrowserSession(user_id=user.id, absolute_expires_at=now() + timedelta(hours=12))
    rotate(session, response)
    db.add(session)
    return describe(db, user)


def logout(session: BrowserSession, response: Response) -> None:
    session.revoked_at = now()
    for name in (SESSION_COOKIE, CSRF_COOKIE):
        response.delete_cookie(
            name, secure=True, httponly=name == SESSION_COOKIE, samesite="lax", path="/"
        )
