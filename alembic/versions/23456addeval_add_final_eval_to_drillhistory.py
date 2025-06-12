"""Add final_eval field to DrillHistory

Revision ID: 23456addeval
Revises: 12345addmoves
Create Date: 2025-06-20 12:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '23456addeval'
down_revision: Union[str, None] = '12345addmoves'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'drillhistory',
        sa.Column('final_eval', sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('drillhistory', 'final_eval')
