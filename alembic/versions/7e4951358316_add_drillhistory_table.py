"""Add DrillHistory table

Revision ID: 7e4951358316
Revises: aff449acc12b
Create Date: 2025-06-01 10:07:09.750737

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7e4951358316"
down_revision: Union[str, None] = "aff449acc12b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "drillhistory",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "drill_position_id",
            sa.Integer(),
            sa.ForeignKey("drillposition.id"),
            nullable=False,
        ),
        sa.Column("result", sa.String(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("drillhistory")
