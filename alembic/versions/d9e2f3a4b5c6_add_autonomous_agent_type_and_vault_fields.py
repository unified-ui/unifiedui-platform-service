"""Add autonomous agent type, vault URIs and last_full_import fields

Revision ID: d9e2f3a4b5c6
Revises: c8601860d5a8
Create Date: 2026-01-09 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9e2f3a4b5c6'
down_revision: Union[str, Sequence[str], None] = 'c8601860d5a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add type column with N8N as default (all existing agents become N8N type)
    op.add_column(
        'autonomous_agents',
        sa.Column('type', sa.String(length=50), nullable=False, server_default='N8N')
    )
    
    # Add primary_key_vault_uri column (nullable for existing records)
    op.add_column(
        'autonomous_agents',
        sa.Column('primary_key_vault_uri', sa.String(length=500), nullable=True)
    )
    
    # Add secondary_key_vault_uri column (nullable for existing records)
    op.add_column(
        'autonomous_agents',
        sa.Column('secondary_key_vault_uri', sa.String(length=500), nullable=True)
    )
    
    # Add last_full_import column (nullable, system-managed)
    op.add_column(
        'autonomous_agents',
        sa.Column('last_full_import', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('autonomous_agents', 'last_full_import')
    op.drop_column('autonomous_agents', 'secondary_key_vault_uri')
    op.drop_column('autonomous_agents', 'primary_key_vault_uri')
    op.drop_column('autonomous_agents', 'type')
