"""rename last_played_at to last_drilled_at

Revision ID: 4f5ff9e87512
Revises: a4370e98dae0
Create Date: 2025-06-05 02:20:02.043777

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4f5ff9e87512"
down_revision: Union[str, None] = "a4370e98dae0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.alter_column(
        "drillposition", "last_played_at", new_column_name="last_drilled_at"
    )


def downgrade():
    op.alter_column(
        "drillposition", "last_drilled_at", new_column_name="last_played_at"
    )
