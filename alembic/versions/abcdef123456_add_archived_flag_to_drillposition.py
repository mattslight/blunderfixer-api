"""Add archived flag to DrillPosition

Revision ID: abcdef123456
Revises: d968b73b020a
Create Date: 2025-06-04 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "abcdef123456"
down_revision: Union[str, None] = "d968b73b020a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "drillposition",
        sa.Column("archived", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("drillposition", "archived")
