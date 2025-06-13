"""Change time_used from int to float

Revision ID: 3f6cf766c526
Revises: 4b81aa1c3803
Create Date: 2025-06-13 17:43:15.535472

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3f6cf766c526"
down_revision: Union[str, None] = "4b81aa1c3803"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "drillposition", "time_used", existing_type=sa.Integer(), type_=sa.Float()
    )


def downgrade() -> None:
    op.alter_column(
        "drillposition", "time_used", existing_type=sa.Float(), type_=sa.Integer()
    )
