"""Alter drill_position.time_used to NUMERIC(5,1)

Revision ID: 82c83a8ff95c
Revises: 3f6cf766c526
Create Date: 2025-06-13 18:17:01.497764

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "82c83a8ff95c"
down_revision: Union[str, None] = "3f6cf766c526"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Alter time_used to NUMERIC(5,1), rounding existing floats
    op.alter_column(
        "drillposition",
        "time_used",
        existing_type=sa.Float(),
        type_=sa.Numeric(5, 1),
        postgresql_using="ROUND(time_used::numeric, 1)",
    )


def downgrade():
    # Revert back to plain float
    op.alter_column(
        "drillposition",
        "time_used",
        existing_type=sa.Numeric(5, 1),
        type_=sa.Float(),
        postgresql_using="time_used::float",
    )
