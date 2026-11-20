import secrets
from datetime import timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.intake_inputs import ClientInvite, Convert, FormSubmission, Inquiry, LeadUpdate
from app.models import Audit, Client, ClientMembership, Project
from app.operations_models import ClientInvitation, Lead, Outbox, Submission
from app.schemas import Redeem
from app.security import digest, now
from app.services import agency


def create(db: Session, data: Inquiry, source: str) -> Lead:
    values = data.model_dump(exclude={"website_confirmation"})
    values["email"] = str(data.email).lower()
    lead = Lead(**values, source=source)
    db.add(lead)
    db.flush()
    db.add(Outbox(event_type="lead.created", aggregate_type="lead", aggregate_id=lead.id))
    return lead


def external(db: Session, data: FormSubmission) -> UUID:
    key = data.source_submission_id
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 1))"), {"key": key})
    signature = digest(data.inquiry.model_dump_json())
    receipt = db.scalar(
        select(Submission).where(
            Submission.source == "google_forms", Submission.source_submission_id == key
        )
    )
    if receipt:
        if receipt.fingerprint != signature:
            raise HTTPException(409, "Submission payload changed")
        return receipt.lead_id
    lead = create(db, data.inquiry, "google_forms")
    db.add(
        Submission(
            source="google_forms", source_submission_id=key, fingerprint=signature, lead_id=lead.id
        )
    )
    return lead.id


def detail(lead: Lead) -> dict[str, Any]:
    return {c.name: getattr(lead, c.name) for c in Lead.__table__.columns}


def get_lead(db: Session, actor: UUID, lead_id: UUID, *, write: bool = False) -> Lead:
    if write:
        agency.guard_operational_write(db)
    agency.manager_roles(db, actor)
    row = db.get(Lead, lead_id, with_for_update=write)
    if row is None:
        raise HTTPException(404, "Lead not found")
    return row


def editable(lead: Lead) -> None:
    if lead.status in {"converted", "rejected"}:
        raise HTTPException(409, "Lead is closed")


def update_lead(db: Session, actor: UUID, lead: Lead, data: LeadUpdate) -> None:
    editable(lead)
    if data.status:
        lead.status = data.status
    if "notes" in data.model_fields_set:
        lead.notes = data.notes
    agency.audit(db, actor, "lead.updated", lead.id, {"status": lead.status})


def assign(db: Session, actor: UUID, lead: Lead, target: UUID | None) -> None:
    editable(lead)
    if target and not agency.roles(db, target):
        raise HTTPException(422, "Assignee must be active agency staff")
    lead.assigned_to = target
    agency.audit(db, actor, "lead.assigned", lead.id, {"user_id": str(target) if target else None})


def convert(db: Session, actor: UUID, lead_id: UUID, data: Convert) -> dict[str, Any]:
    lead = get_lead(db, actor, lead_id, write=True)
    if lead.status != "converted":
        if lead.status not in {"qualified", "proposal_sent"}:
            raise HTTPException(409, "Qualify the lead before conversion")
        client = Client(
            company_name=lead.company_name,
            brand_name=data.brand_name,
            industry=data.industry or lead.industry,
            primary_contact_name=lead.contact_name,
            primary_contact_email=lead.email,
            primary_contact_phone=lead.phone,
        )
        db.add(client)
        db.flush()
        if data.create_initial_project:
            project = Project(client_id=client.id, name=data.initial_project_name, created_by=actor)
            db.add(project)
            db.flush()
            lead.initial_project_id = project.id
        lead.converted_client_id = client.id
        lead.status = "converted"
        db.add(
            Audit(
                actor_id=actor,
                action="lead.converted",
                target_id=lead.id,
                client_id=client.id,
                project_id=lead.initial_project_id,
                details={},
            )
        )
    return {
        "lead_id": lead.id,
        "client_id": lead.converted_client_id,
        "project_id": lead.initial_project_id,
        "status": lead.status,
    }


def issue(db: Session, actor: UUID, client_id: UUID, data: ClientInvite) -> dict[str, Any]:
    agency.guard(db)
    agency.manager_roles(db, actor)
    if db.get(Client, client_id) is None:
        raise HTTPException(404, "Client not found")
    token = secrets.token_urlsafe(40)
    invite = ClientInvitation(
        client_id=client_id,
        email=str(data.email).lower(),
        role=data.role,
        invited_by=actor,
        token_digest=digest(token),
        expires_at=now() + timedelta(days=2),
    )
    db.add(invite)
    db.flush()
    agency.audit(
        db,
        actor,
        "client_invitation.issued",
        invite.id,
        {"client_id": str(client_id), "role": invite.role},
    )
    return {"id": invite.id, "token": token, "expires_at": invite.expires_at}


def redeem_client(
    db: Session, invite: ClientInvitation, data: Redeem, signed_in: UUID | None
) -> UUID:
    agency.manager_roles(db, invite.invited_by)
    if invite.accepted_at or invite.revoked_at or invite.expires_at <= now():
        raise HTTPException(400, "Invitation unavailable")
    user = agency.invited_account(db, invite.email, data, signed_in)
    membership = db.scalar(
        select(ClientMembership).where(
            ClientMembership.user_id == user.id, ClientMembership.client_id == invite.client_id
        )
    )
    if membership and (not membership.is_active or membership.role != invite.role):
        raise HTTPException(409, "Existing membership must be managed separately")
    if membership is None:
        db.add(ClientMembership(user_id=user.id, client_id=invite.client_id, role=invite.role))
    invite.accepted_at = now()
    db.add(
        Audit(
            actor_id=user.id,
            action="client_invitation.accepted",
            target_id=invite.id,
            client_id=invite.client_id,
            details={"role": invite.role},
        )
    )
    return user.id
