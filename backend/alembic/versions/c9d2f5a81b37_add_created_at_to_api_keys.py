"""add created_at to api_keys

Revision ID: c9d2f5a81b37
Revises: b7e41a9c3d25
Create Date: 2026-11-02 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9d2f5a81b37'
down_revision: Union[str, Sequence[str], None] = 'b7e41a9c3d25'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default fills in existing rows with the time of the migration.
    op.add_column(
        'api_keys',
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('api_keys', 'created_at')
