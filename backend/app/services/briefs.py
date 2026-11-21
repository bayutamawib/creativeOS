from collections import defaultdict
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.brief_inputs import BriefEdit, BriefFields, Version
from app.brief_models import Brief, BriefFile, FileAsset, Snapshot, SnapshotFile
from app.models import Client, Project
from app.operations_models import Outbox
from app.project_inputs import Portal
from app.security import now
from app.services import agency, clients, projects


def context(
    db: Session, actor: UUID, project_id: UUID, portal: Portal, *, write: bool = False
) -> Project:
    if write:
        agency.guard_operational_write(db)
    p = projects.access(db, actor, project_id, portal, write=write)
    if portal == "client" and write:
        clients.membership(db, actor, p.client_id, lock=True)
    return p


def get(
    db: Session, actor: UUID, identifier: UUID, portal: Portal, *, write: bool = False
) -> Brief:
    pid = db.scalar(select(Brief.project_id).where(Brief.id == identifier))
    if pid is None:
        raise HTTPException(404, "Brief not found")
    context(db, actor, pid, portal, write=write)
    return db.get_one(Brief, identifier, with_for_update=write)


def fields(row: Brief) -> dict[str, Any]:
    return {"title": row.title, "objective": row.objective, **row.requirements}


def view(db: Session, row: Brief) -> dict[str, Any]:
    return views(db, [row])[0]


def views(db: Session, rows: Sequence[Brief]) -> list[dict[str, Any]]:
    if not rows:
        return []
    keys = [r.id for r in rows]
    attached: dict[UUID, list[UUID]] = defaultdict(list)
    for brief_id, file_id in db.execute(
        select(BriefFile.brief_id, BriefFile.file_id)
        .where(BriefFile.brief_id.in_(keys))
        .order_by(BriefFile.file_id)
    ):
        attached[brief_id].append(file_id)
    snapshots = {
        (s.brief_id, s.version): s.id
        for s in db.execute(
            select(Snapshot.brief_id, Snapshot.version, Snapshot.id)
            .join(Brief, Brief.id == Snapshot.brief_id)
            .where(Brief.id.in_(keys), Snapshot.version == Brief.version)
        )
    }
    return [
        {
            **fields(row),
            "id": row.id,
            "project_id": row.project_id,
            "status": row.status,
            "version": row.version,
            "feedback": row.feedback,
            "attachment_ids": attached[row.id],
            "snapshot_id": snapshots.get((row.id, row.version)),
        }
        for row in rows
    ]


def save_fields(db: Session, row: Brief, data: BriefFields) -> None:
    ids = set(data.attachment_ids)
    if ids:
        allowed = set(
            db.scalars(
                select(FileAsset.id).where(
                    FileAsset.id.in_(ids),
                    FileAsset.project_id == row.project_id,
                    FileAsset.visibility == "client_visible",
                    FileAsset.archived_at.is_(None),
                )
            )
        )
        if ids != allowed:
            raise HTTPException(422, "Attachments must be shared files from this project")
    row.title, row.objective = data.title, data.objective
    row.requirements = data.model_dump(
        mode="json", exclude={"title", "objective", "attachment_ids"}
    )
    db.flush()
    db.execute(delete(BriefFile).where(BriefFile.brief_id == row.id))
    db.add_all(
        [BriefFile(brief_id=row.id, project_id=row.project_id, file_id=i) for i in sorted(ids)]
    )


def create(db: Session, actor: UUID, pid: UUID, portal: Portal, data: BriefFields) -> Brief:
    p = context(db, actor, pid, portal, write=True)
    row = Brief(project_id=p.id, client_id=p.client_id, created_by=actor)
    # Validate attachments before adding an incomplete row to the session.
    row.title, row.objective, row.requirements = data.title, data.objective, {}
    db.add(row)
    save_fields(db, row, data)
    projects.change_log(db, actor, p, "brief.created", row.id)
    return row


def edit(db: Session, actor: UUID, key: UUID, portal: Portal, data: BriefEdit) -> Brief:
    row = get(db, actor, key, portal, write=True)
    if row.version != data.expected_version or row.status not in {
        "draft",
        "revision_requested",
        "approved",
    }:
        raise HTTPException(409, "Brief changed or is closed for editing")
    values = fields(row)
    values["attachment_ids"] = view(db, row)["attachment_ids"]
    values.update(data.model_dump(exclude_unset=True, exclude={"expected_version"}))
    try:
        approved = BriefFields.model_validate(values)
    except ValidationError as err:
        raise HTTPException(422, "Invalid brief fields") from err
    save_fields(db, row, approved)
    row.version += 1
    row.status = "draft"
    projects.change_log(
        db,
        actor,
        db.get_one(Project, row.project_id),
        "brief.edited",
        row.id,
        {"version": row.version},
    )
    return row


def transition(db: Session, actor: UUID, key: UUID, action: str, data: Version) -> Brief:
    portal: Portal = "client" if action == "submit" else "agency"
    row = get(db, actor, key, portal, write=True)
    p = db.get_one(Project, row.project_id)
    if action == "submit":
        clients.require_admin(clients.membership(db, actor, p.client_id))
    states = {
        "submit": ({"draft", "revision_requested"}, "submitted"),
        "start-review": ({"submitted"}, "under_review"),
        "request-revision": ({"submitted", "under_review"}, "revision_requested"),
        "reject": ({"submitted", "under_review"}, "rejected"),
        "approve": ({"submitted", "under_review"}, "approved"),
    }
    before, after = states[action]
    if row.version != data.expected_version or row.status not in before:
        raise HTTPException(409, "Brief version or review state changed")
    if action in {"request-revision", "reject"} and not data.feedback:
        raise HTTPException(422, "Provide review feedback")
    row.version += 1
    row.status = after
    if action == "submit":
        row.submitted_by = actor
    else:
        row.reviewed_by, row.reviewed_at, row.feedback = actor, now(), data.feedback
    if action == "approve":
        client = db.get_one(Client, p.client_id, with_for_update=True)
        files = list(
            db.scalars(
                select(FileAsset)
                .join(BriefFile, BriefFile.file_id == FileAsset.id)
                .where(BriefFile.brief_id == row.id)
                .order_by(FileAsset.id)
            )
        )
        snap = Snapshot(
            brief_id=row.id,
            version=row.version,
            project_id=p.id,
            client_id=p.client_id,
            approved_by=actor,
            fields=fields(row),
            brand={
                "company_name": client.company_name,
                "brand_name": client.brand_name,
                "industry": client.industry,
                "guidelines": client.brand_guidelines,
            },
            attachments=[
                {"id": str(f.id), "name": f.file_name, "sha256": f.sha256, "category": f.category}
                for f in files
            ],
        )
        db.add(snap)
        db.flush()
        db.add_all(
            [SnapshotFile(snapshot_id=snap.id, project_id=p.id, file_id=f.id) for f in files]
        )
        db.add(
            Outbox(
                event_type="brief.approved",
                aggregate_type="brief",
                aggregate_id=row.id,
                payload={"snapshot_id": str(snap.id)},
            )
        )
    projects.change_log(db, actor, p, "brief." + after, row.id, {"version": row.version})
    return row
