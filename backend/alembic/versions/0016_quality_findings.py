"""Store deterministic quality findings separately from generated output."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0016_quality_findings"
down_revision = "0015_video_cover"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_generations", sa.Column("quality_findings", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_generations", "quality_findings")
