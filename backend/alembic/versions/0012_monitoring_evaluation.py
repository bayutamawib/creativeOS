import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0012_monitoring_evaluation"
down_revision = "0011_reports"
branch_labels = None
depends_on = None


def identity():
    return [
        sa.Column("id", sa.UUID, primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.add_column(
        "ai_generations",
        sa.Column("retry_allowance", sa.Integer, server_default="0", nullable=False),
    )
    op.add_column(
        "outbox_events",
        sa.Column("retry_allowance", sa.Integer, server_default="0", nullable=False),
    )
    op.add_column("notifications", sa.Column("claim_expires_at", sa.DateTime(timezone=True)))
    op.create_table(
        "notification_attempts",
        *identity(),
        sa.Column("notification_id", sa.UUID, sa.ForeignKey("notifications.id"), nullable=False),
        sa.Column("run_id", sa.UUID, sa.ForeignKey("workflow_runs.id")),
        sa.Column("attempt", sa.Integer, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String),
        sa.UniqueConstraint("notification_id", "attempt"),
    )
    op.execute("""INSERT INTO notification_attempts(id,created_at,notification_id,run_id,attempt,status,finished_at)
    SELECT n.id,n.created_at,n.id,p.run_id,1,n.delivery_status,n.delivered_at
    FROM notifications n LEFT JOIN processed_events p ON p.event_id=n.event_id AND p.consumer_name='development-inbox'
    WHERE n.channel='development-inbox' AND n.delivery_status='delivered'""")
    op.create_table(
        "ai_evaluations",
        *identity(),
        sa.Column("requested_by", sa.UUID, sa.ForeignKey("users.id"), nullable=False),
        *[
            sa.Column(k, sa.String, nullable=False)
            for k in ("provider", "model", "prompt_version", "dataset_version", "dataset_hash")
        ],
        sa.Column("aggregates", JSONB, nullable=False),
    )
    op.create_table(
        "ai_evaluation_cases",
        *identity(),
        sa.Column("evaluation_id", sa.UUID, sa.ForeignKey("ai_evaluations.id"), nullable=False),
        sa.Column("case_key", sa.String, nullable=False),
        sa.Column("service", sa.String, nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("checks", JSONB, nullable=False),
        sa.Column("sample", JSONB, nullable=False),
        sa.Column("output", JSONB),
        sa.Column("latency_ms", sa.Integer, nullable=False),
        sa.UniqueConstraint("evaluation_id", "case_key"),
    )
    op.create_index(
        "ix_ai_evaluation_cases_evaluation_id", "ai_evaluation_cases", ["evaluation_id"]
    )
    op.create_table(
        "ai_evaluation_reviews",
        *identity(),
        sa.Column("case_id", sa.UUID, sa.ForeignKey("ai_evaluation_cases.id"), nullable=False),
        sa.Column("reviewer_id", sa.UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("rubric", JSONB, nullable=False),
        sa.UniqueConstraint("case_id", "reviewer_id"),
    )


def downgrade() -> None:
    op.drop_table("ai_evaluation_reviews")
    op.drop_table("ai_evaluation_cases")
    op.drop_table("ai_evaluations")
    op.drop_table("notification_attempts")
    op.drop_column("notifications", "claim_expires_at")
    op.drop_column("ai_generations", "retry_allowance")
    op.drop_column("outbox_events", "retry_allowance")
