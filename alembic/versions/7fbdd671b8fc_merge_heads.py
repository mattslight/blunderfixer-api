"""merge heads

Revision ID: 7fbdd671b8fc
Revises: 95063c8527c1, abcdef123456
Create Date: 2025-06-05 02:02:15.801212

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7fbdd671b8fc'
down_revision: Union[str, None] = ('95063c8527c1', 'abcdef123456')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
