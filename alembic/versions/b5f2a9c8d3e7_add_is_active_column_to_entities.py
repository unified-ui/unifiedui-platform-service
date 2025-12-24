"""add_is_active_column_to_entities

Revision ID: b5f2a9c8d3e7
Revises: 8a3e1b9c2d4f
Create Date: 2025-12-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5f2a9c8d3e7'
down_revision: Union[str, None] = '8a3e1b9c2d4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_active column to applications
    op.add_column(
        'applications',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='false')
    )
    
    # Add is_active column to conversations
    op.add_column(
        'conversations',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='false')
    )
    
    # Add is_active column to autonomous_agents
    op.add_column(
        'autonomous_agents',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='false')
    )
    
    # Add is_active column to credentials
    op.add_column(
        'credentials',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='false')
    )
    
    # Add is_active column to development_platforms
    op.add_column(
        'development_platforms',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='false')
    )
    
    # Add is_active column to chat_widgets
    op.add_column(
        'chat_widgets',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='false')
    )


def downgrade() -> None:
    # Remove is_active column from all tables
    op.drop_column('chat_widgets', 'is_active')
    op.drop_column('development_platforms', 'is_active')
    op.drop_column('credentials', 'is_active')
    op.drop_column('autonomous_agents', 'is_active')
    op.drop_column('conversations', 'is_active')
    op.drop_column('applications', 'is_active')
