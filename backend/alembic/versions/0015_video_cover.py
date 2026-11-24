import sqlalchemy as sa

from alembic import op

revision = "0015_video_cover"
down_revision = "0014_schedule_heartbeat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("file_assets", sa.Column("cover_file_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_file_assets_cover_project", "file_assets", "file_assets", ["cover_file_id", "project_id"], ["id", "project_id"])


def downgrade() -> None:
    op.drop_constraint("fk_file_assets_cover_project", "file_assets", type_="foreignkey")
    op.drop_column("file_assets", "cover_file_id")
