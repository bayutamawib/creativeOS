from typing import Any

from fastapi import APIRouter, Request, Response
from sqlalchemy import select

from app.api.deps import Database, Identity
from app.models import User
from app.operations_models import ClientInvitation
from app.schemas import Forgot, Login, Redeem, Reset
from app.security import digest
from app.services import agency, intake, recovery, sessions
from app.services.rate_limit import limit

router = APIRouter(prefix="/auth")


@router.post("/login")
def login(payload: Login, request: Request, response: Response, db: Database) -> dict[str, Any]:
    sessions.same_origin(request)
    limit(db, request, "login", str(payload.email).lower())
    return {"data": sessions.login(db, payload, response)}


@router.get("/me")
def me(db: Database, identity: Identity) -> dict[str, Any]:
    return {"data": sessions.describe(db, db.get_one(User, identity.user_id))}


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Database) -> None:
    sessions.logout(sessions.current(db, request, lock=True), response)


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Database) -> dict[str, bool]:
    sessions.rotate(sessions.current(db, request, lock=True), response)
    return {"renewed": True}


@router.post("/register", status_code=201)
def register(payload: Redeem, request: Request, db: Database) -> dict[str, Any]:
    sessions.same_origin(request)
    limit(db, request, "register", payload.token.get_secret_value())
    user_id = (
        sessions.current(db, request).user_id
        if request.cookies.get(sessions.SESSION_COOKIE)
        else None
    )
    agency.guard(db)
    invite = db.scalar(
        select(ClientInvitation)
        .where(ClientInvitation.token_digest == digest(payload.token.get_secret_value()))
        .with_for_update()
    )
    if invite:
        return {"data": {"id": intake.redeem_client(db, invite, payload, user_id)}}
    return {"data": {"id": agency.redeem(db, payload, user_id)}}


@router.post("/forgot-password", status_code=202)
def forgot(payload: Forgot, request: Request, db: Database) -> dict[str, str]:
    sessions.same_origin(request)
    limit(db, request, "forgot", str(payload.email).lower())
    recovery.request_reset(db, str(payload.email))
    return {"message": "If the account is active, reset instructions will be delivered"}


@router.post("/reset-password", status_code=204)
def reset(payload: Reset, request: Request, db: Database) -> None:
    sessions.same_origin(request)
    limit(db, request, "reset", payload.token.get_secret_value())
    recovery.reset_password(
        db, payload.token.get_secret_value(), payload.password.get_secret_value()
    )
