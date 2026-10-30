"""use timezone aware created_at

Revision ID: b7e41a9c3d25
Revises: 6cdf7cde6985
Create Date: 2026-10-31 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e41a9c3d25'
down_revision: Union[str, Sequence[str], None] = '6cdf7cde6985'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Existing values were written by the app running in a UTC container,
    # so they are read as UTC when converted.
    op.alter_column(
        'users',
        'created_at',
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'users',
        'created_at',
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )