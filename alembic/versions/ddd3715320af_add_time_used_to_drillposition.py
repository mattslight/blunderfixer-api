"""add time_used to DrillPosition

Revision ID: ddd3715320af
Revises: ee8f8ae495cd
Create Date: 2025-06-13 11:21:26.322483

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ddd3715320af'
down_revision: Union[str, None] = 'ee8f8ae495cd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'drillposition',
        sa.Column('time_used', sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('drillposition', 'time_used')
