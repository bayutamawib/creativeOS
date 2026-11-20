import sqlalchemy as sa

from alembic import op

revision = "0013_dispatch_error"
down_revision = "0012_monitoring_evaluation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("outbox_events", sa.Column("error_code", sa.String))
    op.add_column("outbox_events", sa.Column("failed_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("outbox_events", "failed_at")
    op.drop_column("outbox_events", "error_code")
