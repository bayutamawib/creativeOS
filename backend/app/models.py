from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Entity(Base):
    __abstract__ = True
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Entity):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(255), unique=True)
    full_name: Mapped[str] = mapped_column(String(150))
    password_hash: Mapped[str]
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("email = lower(trim(email))", name="ck_users_normalized_email"),
    )


AGENCY_ROLES = ("admin", "agency_manager", "team_member")
AGENCY_ROLE_CHECK = "role IN ('admin','agency_manager','team_member')"


class AgencyMembership(Entity):
    __tablename__ = "agency_memberships"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(30))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    __table_args__ = (UniqueConstraint("user_id", "role"), CheckConstraint(AGENCY_ROLE_CHECK))


class Client(Entity):
    __tablename__ = "clients"
    company_name: Mapped[str] = mapped_column(String(200))

    brand_name: Mapped[str | None] = mapped_column(String(200))
    industry: Mapped[str | None] = mapped_column(String(100))
    primary_contact_name: Mapped[str | None] = mapped_column(String(150))
    primary_contact_email: Mapped[str | None] = mapped_column(String(255))
    primary_contact_phone: Mapped[str | None] = mapped_column(String(30))


class ClientMembership(Entity):
    __tablename__ = "client_memberships"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id"))
    role: Mapped[str] = mapped_column(String(30))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    __table_args__ = (
        UniqueConstraint("user_id", "client_id"),
        UniqueConstraint("id", "client_id"),
        CheckConstraint("role IN ('client_admin','client_member')"),
    )


class Project(Entity):
    __tablename__ = "projects"
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None]
    service_type: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(server_default="draft")
    priority: Mapped[str] = mapped_column(server_default="medium")
    start_date: Mapped[date | None]
    due_date: Mapped[date | None]
    budget: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("id", "client_id"),
        CheckConstraint("due_date >= start_date", name="ck_project_dates"),
        CheckConstraint(
            "status IN ('draft','planning','in_progress','in_review','completed','on_hold','cancelled')",
            name="ck_project_status",
        ),
        CheckConstraint("priority in ('low','medium','high','urgent')", name="ck_project_priority"),
    )


class Delegation(Entity):
    __tablename__ = "project_approval_delegations"
    client_id: Mapped[UUID]
    project_id: Mapped[UUID]
    grantee_membership_id: Mapped[UUID]
    granted_by_membership_id: Mapped[UUID]
    revoked_by_membership_id: Mapped[UUID | None]
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(["project_id", "client_id"], ["projects.id", "projects.client_id"]),
        ForeignKeyConstraint(
            ["grantee_membership_id", "client_id"],
            ["client_memberships.id", "client_memberships.client_id"],
        ),
        ForeignKeyConstraint(
            ["granted_by_membership_id", "client_id"],
            ["client_memberships.id", "client_memberships.client_id"],
        ),
        ForeignKeyConstraint(
            ["revoked_by_membership_id", "client_id"],
            ["client_memberships.id", "client_memberships.client_id"],
        ),
        Index(
            "uq_active_project_delegate",
            "project_id",
            "grantee_membership_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )


class BrowserSession(Entity):
    __tablename__ = "sessions"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_digest: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgencyInvitation(Entity):
    __tablename__ = "agency_invitations"
    email: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30))
    invited_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint(AGENCY_ROLE_CHECK),)


class Audit(Entity):
    __tablename__ = "activity_logs"
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100))
    target_id: Mapped[UUID]
    client_id: Mapped[UUID | None] = mapped_column(ForeignKey("clients.id"))
    project_id: Mapped[UUID | None] = mapped_column(ForeignKey("projects.id"))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB)


class OperationsSettings(Base):
    __tablename__ = "agency_operational_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    timezone: Mapped[str] = mapped_column(String(80))
    __table_args__ = (CheckConstraint("id = 1"),)


class PasswordReset(Entity):
    __tablename__ = "password_reset_tokens"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthRateLimit(Base):
    __tablename__ = "auth_rate_limits"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    attempts: Mapped[int]
