"""add allow_api_keys to autonomous_agents

Revision ID: 2dcb01103929
Revises: g1a2b3c4d5e6
Create Date: 2026-02-08 00:21:43.636578

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2dcb01103929'
down_revision: Union[str, Sequence[str], None] = 'g1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('autonomous_agents', sa.Column('allow_api_keys', sa.Boolean(), nullable=False, server_default=sa.text('false')))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('autonomous_agents', 'allow_api_keys')
