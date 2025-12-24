"""add_application_type_column

Revision ID: b3834d227094
Revises: c9d8e7f6a5b4
Create Date: 2025-12-24 22:28:06.961528

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b3834d227094'
down_revision: Union[str, Sequence[str], None] = 'c9d8e7f6a5b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add type column to applications table."""
    # Create user favorites tables
    op.create_table('application_user_favorites',
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=50), nullable=False),
        sa.Column('application_id', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('updated_by', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('tenant_id', 'user_id', 'application_id')
    )
    op.create_index('ix_auf_application', 'application_user_favorites', ['application_id'], unique=False)
    op.create_index('ix_auf_user', 'application_user_favorites', ['user_id'], unique=False)
    
    op.create_table('autonomous_agent_user_favorites',
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=50), nullable=False),
        sa.Column('autonomous_agent_id', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('updated_by', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['autonomous_agent_id'], ['autonomous_agents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('tenant_id', 'user_id', 'autonomous_agent_id')
    )
    op.create_index('ix_aauf_autonomous_agent', 'autonomous_agent_user_favorites', ['autonomous_agent_id'], unique=False)
    op.create_index('ix_aauf_user', 'autonomous_agent_user_favorites', ['user_id'], unique=False)
    
    op.create_table('conversation_user_favorites',
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=50), nullable=False),
        sa.Column('conversation_id', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('updated_by', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('tenant_id', 'user_id', 'conversation_id')
    )
    op.create_index('ix_cuf_conversation', 'conversation_user_favorites', ['conversation_id'], unique=False)
    op.create_index('ix_cuf_user', 'conversation_user_favorites', ['user_id'], unique=False)
    
    op.create_table('development_platform_user_favorites',
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=50), nullable=False),
        sa.Column('development_platform_id', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('updated_by', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['development_platform_id'], ['development_platforms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('tenant_id', 'user_id', 'development_platform_id')
    )
    op.create_index('ix_dpuf_development_platform', 'development_platform_user_favorites', ['development_platform_id'], unique=False)
    op.create_index('ix_dpuf_user', 'development_platform_user_favorites', ['user_id'], unique=False)
    
    # Add type column to applications - first as nullable
    op.add_column('applications', sa.Column('type', sa.String(length=50), nullable=True))
    
    # Set default value for existing rows
    op.execute("UPDATE applications SET type = 'N8N' WHERE type IS NULL")
    
    # Now make the column non-nullable and add check constraint
    op.alter_column('applications', 'type', nullable=False)
    op.create_check_constraint(
        'application_type_check',
        'applications',
        "type IN ('N8N', 'MICROSOFT_FOUNDRY', 'REST_API')"
    )


def downgrade() -> None:
    """Downgrade schema - remove type column from applications table."""
    # Drop check constraint and column
    op.drop_constraint('application_type_check', 'applications', type_='check')
    op.drop_column('applications', 'type')
    
    # Drop user favorites tables
    op.drop_index('ix_dpuf_user', table_name='development_platform_user_favorites')
    op.drop_index('ix_dpuf_development_platform', table_name='development_platform_user_favorites')
    op.drop_table('development_platform_user_favorites')
    
    op.drop_index('ix_cuf_user', table_name='conversation_user_favorites')
    op.drop_index('ix_cuf_conversation', table_name='conversation_user_favorites')
    op.drop_table('conversation_user_favorites')
    
    op.drop_index('ix_aauf_user', table_name='autonomous_agent_user_favorites')
    op.drop_index('ix_aauf_autonomous_agent', table_name='autonomous_agent_user_favorites')
    op.drop_table('autonomous_agent_user_favorites')
    
    op.drop_index('ix_auf_user', table_name='application_user_favorites')
    op.drop_index('ix_auf_application', table_name='application_user_favorites')
    op.drop_table('application_user_favorites')
