import sqlalchemy as sa

from alembic import op

revision = "0010_revision_files"
down_revision = "0009_reviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "revision_files",
        sa.Column("revision_id", sa.UUID, sa.ForeignKey("content_revisions.id"), primary_key=True),
        sa.Column("file_id", sa.UUID, sa.ForeignKey("file_assets.id"), primary_key=True),
    )
    op.execute(
        "CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON revision_files FOR EACH ROW EXECUTE FUNCTION creative_immutable()"
    )


def downgrade() -> None:
    op.drop_table("revision_files")
