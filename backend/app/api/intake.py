import secrets
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request
from sqlalchemy import select

from app.api.deps import Database, Identity
from app.config import settings
from app.intake_inputs import Assign, ClientInvite, Convert, FormSubmission, Inquiry, LeadUpdate
from app.models import Audit, Client, ClientMembership, User
from app.operations_models import ClientInvitation, Lead
from app.security import now
from app.services import agency, clients, intake, sessions, workflows
from app.services.rate_limit import limit

router = APIRouter()


@router.post("/public/inquiries", status_code=201)
def inquire(data: Inquiry, request: Request, db: Database) -> dict[str, Any]:
    sessions.same_origin(request)
    limit(db, request, "inquiry", str(data.email).lower())
    lead = intake.create(db, data, "client_portal")
    return {
        "data": {
            "id": lead.id,
            "status": lead.status,
            "message": "Your inquiry has been submitted successfully.",
        }
    }


@router.post("/integrations/google-forms/submissions")
def external(
    data: FormSubmission, db: Database, x_forms_key: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    if not secrets.compare_digest(
        (x_forms_key or "").encode(), workflows.secret(settings().forms_key).encode()
    ):
        raise HTTPException(403, "Integration credential required")
    return {"data": {"id": intake.external(db, data)}}


@router.post("/leads", status_code=201)
def manual(data: Inquiry, db: Database, identity: Identity) -> dict[str, Any]:
    agency.guard_operational_write(db)
    agency.manager_roles(db, identity.user_id)
    lead = intake.create(db, data, "manual")
    agency.audit(db, identity.user_id, "lead.created", lead.id, {})
    return {"data": intake.detail(lead)}


@router.get("/leads")
def leads(
    db: Database,
    identity: Identity,
    status: str | None = None,
    q: Annotated[str, Query(max_length=200)] = "",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    agency.manager_roles(db, identity.user_id)
    stmt = select(Lead)
    if q.strip():
        stmt = stmt.where(
            Lead.company_name.icontains(q.strip(), autoescape=True)
            | Lead.email.icontains(q.strip(), autoescape=True)
            | Lead.contact_name.icontains(q.strip(), autoescape=True)
        )
    if status:
        stmt = stmt.where(Lead.status == status)
    rows = db.scalars(
        stmt.order_by(Lead.created_at.desc(), Lead.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return {"data": [intake.detail(row) for row in rows]}


@router.get("/leads/{lead_id}")
def detail(lead_id: UUID, db: Database, identity: Identity) -> dict[str, Any]:
    return {"data": intake.detail(intake.get_lead(db, identity.user_id, lead_id))}


@router.patch("/leads/{lead_id}")
def update(lead_id: UUID, data: LeadUpdate, db: Database, identity: Identity) -> dict[str, Any]:
    lead = intake.get_lead(db, identity.user_id, lead_id, write=True)
    intake.update_lead(db, identity.user_id, lead, data)
    db.flush()
    return {"data": intake.detail(lead)}


@router.post("/leads/{lead_id}/reject", status_code=204)
def reject(lead_id: UUID, db: Database, identity: Identity) -> None:
    lead = intake.get_lead(db, identity.user_id, lead_id, write=True)
    intake.editable(lead)
    lead.status = "rejected"
    agency.audit(db, identity.user_id, "lead.rejected", lead.id, {})


@router.post("/leads/{lead_id}/assign", status_code=204)
def assign(lead_id: UUID, data: Assign, db: Database, identity: Identity) -> None:
    lead = intake.get_lead(db, identity.user_id, lead_id, write=True)
    intake.assign(db, identity.user_id, lead, data.user_id)


@router.post("/leads/{lead_id}/convert")
def convert(lead_id: UUID, data: Convert, db: Database, identity: Identity) -> dict[str, Any]:
    return {"data": intake.convert(db, identity.user_id, lead_id, data)}


@router.get("/clients")
def directory(db: Database, identity: Identity) -> dict[str, Any]:
    agency.manager_roles(db, identity.user_id)
    return {
        "data": [
            {"id": c.id, "company_name": c.company_name, "email": c.primary_contact_email}
            for c in db.scalars(select(Client).order_by(Client.company_name))
        ]
    }


@router.post("/clients/{client_id}/invitations", status_code=201)
def invite(client_id: UUID, data: ClientInvite, db: Database, identity: Identity) -> dict[str, Any]:
    return {"data": intake.issue(db, identity.user_id, client_id, data)}


@router.get("/clients/{client_id}/invitations")
def invitations(client_id: UUID, db: Database, identity: Identity) -> dict[str, Any]:
    agency.manager_roles(db, identity.user_id)
    rows = db.scalars(
        select(ClientInvitation)
        .where(ClientInvitation.client_id == client_id)
        .order_by(ClientInvitation.created_at.desc())
    )
    return {
        "data": [
            {
                k: getattr(row, k)
                for k in ("id", "email", "role", "expires_at", "accepted_at", "revoked_at")
            }
            for row in rows
        ]
    }


@router.post("/clients/{client_id}/invitations/{invitation_id}/revoke", status_code=204)
def revoke(client_id: UUID, invitation_id: UUID, db: Database, identity: Identity) -> None:
    agency.guard(db)
    agency.manager_roles(db, identity.user_id)
    row = db.get(ClientInvitation, invitation_id, with_for_update=True)
    if not row or row.client_id != client_id:
        raise HTTPException(404, "Invitation not found")
    if row.accepted_at:
        raise HTTPException(409, "Invitation already accepted")
    if not row.revoked_at:
        row.revoked_at = now()
        agency.audit(
            db, identity.user_id, "client_invitation.revoked", row.id, {"client_id": str(client_id)}
        )


@router.get("/leads/{lead_id}/activity")
def activity(lead_id: UUID, db: Database, identity: Identity) -> dict[str, Any]:
    lead = intake.get_lead(db, identity.user_id, lead_id)
    rows = db.scalars(
        select(Audit).where(Audit.target_id == lead.id).order_by(Audit.created_at.desc())
    )
    return {"data": [{"action": r.action, "occurred_at": r.created_at} for r in rows]}


@router.get("/clients/{client_id}/members")
def client_members(
    client_id: UUID,
    db: Database,
    identity: Identity,
    portal: Literal["agency", "client"] = "agency",
) -> dict[str, Any]:
    if portal == "agency":
        agency.manager_roles(db, identity.user_id)
    else:
        clients.require_admin(clients.membership(db, identity.user_id, client_id))
    rows = db.execute(
        select(ClientMembership, User)
        .join(User)
        .where(ClientMembership.client_id == client_id)
        .order_by(User.full_name)
    )
    return {
        "data": [
            {
                "id": m.id,
                "name": u.full_name,
                "role": m.role,
                "is_active": m.is_active and u.is_active,
            }
            for m, u in rows
        ]
    }
