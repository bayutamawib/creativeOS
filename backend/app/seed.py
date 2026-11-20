"""Explicit local demo seed. Read passwords from stdin, never from process arguments."""

import json
import sys
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import engine
from app.models import AgencyMembership, Audit, Client, ClientMembership, Project, User
from app.security import hash_password
from app.services.agency import guard


def demo_id(name: str) -> UUID:
    return uuid5(NAMESPACE_URL, "urn:creativeos:development:" + name)


AGENCY = {"admin": "admin", "manager": "agency_manager", "producer": "team_member"}
CLIENTS = {
    "studio": ("Northline Studio", "lead", "reviewer"),
    "press": ("Clover Press", "publisher", "editor"),
}


def seed(db: Session, passwords: dict[str, str]) -> None:
    guard(db)
    users: dict[str, User] = {}
    created: set[str] = set()
    names = [*AGENCY, *(name for _, admin, member in CLIENTS.values() for name in (admin, member))]
    for name in names:
        email = f"{name}@example.com"
        user = db.get(User, demo_id(name))
        if user is None:
            if db.scalar(select(User.id).where(User.email == email)):
                raise ValueError("Demo identity conflicts with an existing account")
            user = User(
                id=demo_id(name),
                full_name=name.title(),
                email=email,
                password_hash=hash_password(passwords[email]),
            )
            db.add(user)
            created.add(name)
        users[name] = user
    db.flush()
    for name, role in AGENCY.items():
        identifier = demo_id(name + "-agency")
        if name in created:
            db.add(AgencyMembership(id=identifier, user_id=users[name].id, role=role))
            db.add(
                Audit(
                    action="seed.agency_membership",
                    target_id=users[name].id,
                    details={"role": role, "source": "local_seed"},
                )
            )
    for key, (company, admin, member) in CLIENTS.items():
        client_id = demo_id(key)
        if db.get(Client, client_id) is None:
            db.add(Client(id=client_id, company_name=company))
            db.flush()
        for name, role in [(admin, "client_admin"), (member, "client_member")]:
            identifier = demo_id(name + "-client")
            if name in created:
                db.add(
                    ClientMembership(
                        id=identifier, user_id=users[name].id, client_id=client_id, role=role
                    )
                )
                db.add(
                    Audit(
                        action="seed.client_membership",
                        target_id=users[name].id,
                        client_id=client_id,
                        details={"role": role, "source": "local_seed"},
                    )
                )
        for title in ("Brand identity", "Launch campaign"):
            identifier = demo_id(key + title)
            if db.get(Project, identifier) is None:
                db.add(Project(id=identifier, client_id=client_id, name=title))


if __name__ == "__main__":
    if settings().app_env != "development":
        raise SystemExit("Demo seeding requires development mode")
    with Session(engine()) as session, session.begin():
        seed(session, json.load(sys.stdin))
    print("Synthetic workspaces seeded")
