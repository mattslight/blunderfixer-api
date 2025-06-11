"""Add winning_lines field to DrillPosition

Revision ID: ee8f8ae495cd
Revises: 500c4862791a
Create Date: 2025-06-15 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ee8f8ae495cd'
down_revision: Union[str, None] = '500c4862791a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'drillposition',
        sa.Column('winning_lines', postgresql.JSON(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('drillposition', 'winning_lines')
