"""merge drill time and moves branches

Revision ID: 4b81aa1c3803
Revises: 12345addmoves, ddd3715320af
Create Date: 2025-06-13 17:05:54.468084

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b81aa1c3803'
down_revision: Union[str, None] = ('12345addmoves', 'ddd3715320af')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
