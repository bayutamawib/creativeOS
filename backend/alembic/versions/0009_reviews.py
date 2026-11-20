import sqlalchemy as sa

from alembic import op

revision = "0009_reviews"
down_revision = "0008_file_provider_ref"
branch_labels = None
depends_on = None


def columns():
    return [
        sa.Column("id", sa.UUID, primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("content_item_id", sa.UUID, nullable=False),
        sa.Column("revision_id", sa.UUID, nullable=False),
        sa.ForeignKeyConstraint(
            ["content_item_id", "revision_id"],
            ["content_revisions.content_item_id", "content_revisions.id"],
        ),
    ]


def upgrade() -> None:
    op.alter_column("content_revisions", "source_generation_id", nullable=True)
    op.create_table(
        "content_approvals",
        *columns(),
        sa.Column("stage", sa.String, nullable=False),
        sa.Column("decision", sa.String, nullable=False, server_default="pending"),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("decided_by", sa.UUID, sa.ForeignKey("users.id")),
        sa.Column("membership_id", sa.UUID, sa.ForeignKey("client_memberships.id")),
        sa.Column("delegation_id", sa.UUID, sa.ForeignKey("project_approval_delegations.id")),
        sa.UniqueConstraint("revision_id", "stage"),
        sa.CheckConstraint("stage in ('client','internal')"),
        sa.CheckConstraint(
            "(decision in ('pending','superseded') and decided_by is null and decided_at is null) or (decision in ('approved','revision_requested','rejected') and decided_by is not null and decided_at is not null)"
        ),
    )
    op.create_table(
        "content_feedback",
        *columns(),
        sa.Column("author_id", sa.UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("message", sa.String, nullable=False),
        sa.Column("visibility", sa.String, nullable=False),
        sa.CheckConstraint("visibility in ('client_visible','internal')"),
    )


def downgrade() -> None:
    op.alter_column("content_revisions", "source_generation_id", nullable=False)
    op.drop_table("content_feedback")
    op.drop_table("content_approvals")
