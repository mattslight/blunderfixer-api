"""Add moves field to DrillHistory

Revision ID: 12345addmoves
Revises: ee8f8ae495cd
Create Date: 2025-06-20 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '12345addmoves'
down_revision: Union[str, None] = 'ee8f8ae495cd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'drillhistory',
        sa.Column('moves', postgresql.JSON(), nullable=False, server_default='[]'),
    )


def downgrade() -> None:
    op.drop_column('drillhistory', 'moves')
