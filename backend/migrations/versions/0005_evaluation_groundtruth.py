"""Add explicit abstention ground truth for evaluation cases."""

import sqlalchemy as sa
from alembic import op

revision = "0005_evaluation_groundtruth"
down_revision = "bd572c04c83c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("evaluation_cases", sa.Column("expected_abstention", sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column("evaluation_cases", "expected_abstention")
