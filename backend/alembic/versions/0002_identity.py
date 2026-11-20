"""identity

Revision ID: 0002_identity
Revises: 0001_foundation
Create Date: 2026-11-20 15:19:07.172239

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_identity"
down_revision: str | Sequence[str] | None = "0001_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "agency_operational_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timezone", sa.String(length=80), nullable=False),
        sa.CheckConstraint("id = 1"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "clients",
        sa.Column("company_name", sa.String(length=200), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("email = lower(trim(email))", name="ck_users_normalized_email"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "agency_invitations",
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("invited_by", sa.Uuid(), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("role IN ('admin','agency_manager','team_member')"),
        sa.ForeignKeyConstraint(
            ["invited_by"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_digest"),
    )
    op.create_table(
        "agency_memberships",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("role IN ('admin','agency_manager','team_member')"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "role"),
    )
    op.create_table(
        "client_memberships",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("role IN ('client_admin','client_member')"),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "client_id"),
        sa.UniqueConstraint("user_id", "client_id"),
    )
    op.create_table(
        "projects",
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "client_id"),
    )
    op.create_index(op.f("ix_projects_client_id"), "projects", ["client_id"], unique=False)
    op.create_table(
        "sessions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("csrf_digest", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_digest"),
    )
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)
    op.create_table(
        "activity_logs",
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=True),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "project_approval_delegations",
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("grantee_membership_id", sa.Uuid(), nullable=False),
        sa.Column("granted_by_membership_id", sa.Uuid(), nullable=False),
        sa.Column("revoked_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["granted_by_membership_id", "client_id"],
            ["client_memberships.id", "client_memberships.client_id"],
        ),
        sa.ForeignKeyConstraint(
            ["grantee_membership_id", "client_id"],
            ["client_memberships.id", "client_memberships.client_id"],
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "client_id"],
            ["projects.id", "projects.client_id"],
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by_membership_id", "client_id"],
            ["client_memberships.id", "client_memberships.client_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_active_project_delegate",
        "project_approval_delegations",
        ["project_id", "grantee_membership_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    # ### end Alembic commands ###

    # Preserve grant history on membership loss, including maintenance SQL.
    op.execute("""
        CREATE FUNCTION close_invalid_approval_grants() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.is_active AND OLD.role = 'client_member'
               AND (NOT NEW.is_active OR NEW.role <> 'client_member') THEN
                WITH closed AS (
                    UPDATE project_approval_delegations SET revoked_at = now()
                    WHERE grantee_membership_id = OLD.id AND revoked_at IS NULL
                    RETURNING id, client_id, project_id
                )
                INSERT INTO activity_logs (id, actor_id, action, target_id, client_id, project_id, details)
                SELECT gen_random_uuid(), nullif(current_setting('creative.actor_id', true),'')::uuid,
                    'delegation.invalidated', id, client_id, project_id,
                    jsonb_build_object('membership_id', OLD.id, 'database_role', current_user)
                FROM closed;
            END IF;
            RETURN NEW;
        END $$;
    """)
    op.execute("""CREATE TRIGGER membership_approval_invalidation
        AFTER UPDATE OF role, is_active ON client_memberships
        FOR EACH ROW EXECUTE FUNCTION close_invalid_approval_grants()""")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER membership_approval_invalidation ON client_memberships")
    op.execute("DROP FUNCTION close_invalid_approval_grants()")
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(
        "uq_active_project_delegate",
        table_name="project_approval_delegations",
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.drop_table("project_approval_delegations")
    op.drop_table("activity_logs")
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_table("sessions")
    op.drop_index(op.f("ix_projects_client_id"), table_name="projects")
    op.drop_table("projects")
    op.drop_table("client_memberships")
    op.drop_table("agency_memberships")
    op.drop_table("agency_invitations")
    op.drop_table("users")
    op.drop_table("clients")
    op.drop_table("agency_operational_settings")
    # ### end Alembic commands ###
