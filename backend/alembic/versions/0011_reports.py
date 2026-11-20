import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0011_reports"
down_revision = "0010_revision_files"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.UUID, primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("project_id", sa.UUID, nullable=False),
        sa.Column("client_id", sa.UUID, nullable=False),
        sa.Column("report_type", sa.String, nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("metrics", JSONB, nullable=False),
        sa.Column("provenance", JSONB, nullable=False),
        sa.Column("narrative", sa.String),
        sa.Column("version", sa.Integer, server_default="1", nullable=False),
        sa.Column("requested_by", sa.UUID, sa.ForeignKey("users.id")),
        sa.Column("service_identity", sa.String),
        sa.Column("published_by", sa.UUID, sa.ForeignKey("users.id")),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["project_id", "client_id"], ["projects.id", "projects.client_id"]),
        sa.UniqueConstraint("id", "project_id"),
        sa.UniqueConstraint("project_id", "report_type", "period_start", "period_end"),
        sa.CheckConstraint("period_end >= period_start"),
        sa.CheckConstraint("(requested_by is null) <> (service_identity is null)"),
        sa.CheckConstraint(
            "status in ('generating','draft','ready_for_review','published','failed')"
        ),
        sa.CheckConstraint(
            "(status='published') = (published_at is not null) and (published_at is null) = (published_by is null)"
        ),
    )
    op.create_index("ix_reports_project_id", "reports", ["project_id"])
    op.create_table(
        "scheduled_reports",
        sa.Column("run_id", sa.UUID, sa.ForeignKey("workflow_runs.id"), primary_key=True),
        sa.Column("report_id", sa.UUID, sa.ForeignKey("reports.id"), primary_key=True),
    )
    op.add_column("ai_generations", sa.Column("report_id", sa.UUID))
    op.alter_column("ai_generations", "snapshot_id", nullable=True)
    op.create_foreign_key(
        "fk_generation_report",
        "ai_generations",
        "reports",
        ["report_id", "project_id"],
        ["id", "project_id"],
    )
    op.create_check_constraint(
        "ck_generation_input",
        "ai_generations",
        "(report_id is null) = (snapshot_id is not null) and (generation_type='report_summary') = (report_id is not null)",
    )
    op.execute("""CREATE FUNCTION guard_report_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF OLD.status='published' OR (OLD.project_id,OLD.client_id,OLD.period_start,OLD.period_end,OLD.report_type,OLD.metrics,OLD.provenance)
        IS DISTINCT FROM (NEW.project_id,NEW.client_id,NEW.period_start,NEW.period_end,NEW.report_type,NEW.metrics,NEW.provenance)
      THEN RAISE EXCEPTION 'report evidence is immutable'; END IF;
      RETURN NEW;
    END $$""")
    op.execute(
        "CREATE TRIGGER reports_preserve BEFORE UPDATE ON reports FOR EACH ROW EXECUTE FUNCTION guard_report_evidence()"
    )


def downgrade() -> None:
    op.drop_constraint("ck_generation_input", "ai_generations")
    op.drop_constraint("fk_generation_report", "ai_generations")
    op.alter_column("ai_generations", "snapshot_id", nullable=False)
    op.drop_column("ai_generations", "report_id")
    op.drop_table("scheduled_reports")
    op.drop_table("reports")
    op.execute("DROP FUNCTION guard_report_evidence()")
