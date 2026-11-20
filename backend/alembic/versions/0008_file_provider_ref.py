"""Store private external file references and preserve existing local UUID keys."""

import sqlalchemy as sa

from alembic import op

revision = "0008_file_provider_ref"
down_revision = "0007_studio"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("file_assets", sa.Column("provider_ref", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("file_assets", "provider_ref")
