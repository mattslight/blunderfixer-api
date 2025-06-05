"""Add winning moves columns

Revision ID: 500c4862791a
Revises: 4f5ff9e87512
Create Date: 2025-06-05 12:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '500c4862791a'
down_revision: Union[str, None] = '4f5ff9e87512'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'drillposition',
        sa.Column('has_one_winning_move', sa.Boolean(), nullable=False, server_default='false'),
    )
    op.add_column(
        'drillposition',
        sa.Column('winning_moves', postgresql.JSON(), nullable=True),
    )
    op.add_column(
        'drillposition',
        sa.Column('losing_move', sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('drillposition', 'losing_move')
    op.drop_column('drillposition', 'winning_moves')
    op.drop_column('drillposition', 'has_one_winning_move')
