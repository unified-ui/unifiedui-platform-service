"""add_chat_widgets_tables

Revision ID: 8a3e1b9c2d4f
Revises: 759ba22ae015
Create Date: 2025-12-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8a3e1b9c2d4f'
down_revision: Union[str, None] = '759ba22ae015'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create chat_widgets table
    op.create_table(
        'chat_widgets',
        sa.Column('id', sa.String(100), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.String(2000), nullable=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('type', sa.String(50), nullable=True),
        sa.Column('config', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('created_by', sa.String(50), nullable=True),
        sa.Column('updated_by', sa.String(50), nullable=True),
    )
    
    # Create index for tenant_id
    op.create_index('ix_chat_widgets_tenant', 'chat_widgets', ['tenant_id'])
    
    # Create chat_widget_members table
    op.create_table(
        'chat_widget_members',
        sa.Column('id', sa.String(100), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('chat_widget_id', sa.String(36), sa.ForeignKey('chat_widgets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('principal_id', sa.String(50), nullable=False),
        sa.Column('principal_type', sa.String(20), nullable=False),
        sa.Column('role', sa.String(10), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('created_by', sa.String(50), nullable=True),
        sa.Column('updated_by', sa.String(50), nullable=True),
        sa.UniqueConstraint('chat_widget_id', 'principal_id', 'principal_type', name='uq_chat_widget_members'),
        sa.CheckConstraint("principal_type IN ('IDENTITY_USER', 'IDENTITY_GROUP', 'CUSTOM_GROUP')", name='ck_chat_widget_members_principal_type'),
        sa.CheckConstraint("role IN ('READ', 'WRITE', 'ADMIN')", name='ck_chat_widget_members_role'),
    )
    
    # Create indexes for chat_widget_members
    op.create_index('ix_cwm_chat_widget', 'chat_widget_members', ['chat_widget_id'])
    op.create_index('ix_cwm_principal', 'chat_widget_members', ['principal_id'])
    
    # Update tenant_role check constraint to include new CHAT_WIDGETS permissions
    # Drop the old constraint (named 'tenant_role') and recreate with new values
    op.drop_constraint('tenant_role', 'tenant_member_roles', type_='check')
    op.create_check_constraint(
        'tenant_role',
        'tenant_member_roles',
        "role IN ('READER', 'GLOBAL_ADMIN', 'CUSTOM_GROUPS_ADMIN', 'CUSTOM_GROUP_CREATOR', 'APPLICATIONS_ADMIN', 'APPLICATIONS_CREATOR', 'CREDENTIALS_ADMIN', 'CREDENTIALS_CREATOR', 'CONVERSATIONS_ADMIN', 'CONVERSATIONS_CREATOR', 'AUTONOMOUS_AGENTS_ADMIN', 'AUTONOMOUS_AGENTS_CREATOR', 'DEVELOPMENT_PLATFORMS_ADMIN', 'DEVELOPMENT_PLATFORMS_CREATOR', 'CHAT_WIDGETS_ADMIN', 'CHAT_WIDGETS_CREATOR')"
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_cwm_principal', table_name='chat_widget_members')
    op.drop_index('ix_cwm_chat_widget', table_name='chat_widget_members')
    op.drop_index('ix_chat_widgets_tenant', table_name='chat_widgets')
    
    # Drop tables
    op.drop_table('chat_widget_members')
    op.drop_table('chat_widgets')
    
    # Restore old tenant_role constraint
    op.drop_constraint('tenant_role', 'tenant_member_roles', type_='check')
    op.create_check_constraint(
        'tenant_role',
        'tenant_member_roles',
        "role IN ('READER', 'GLOBAL_ADMIN', 'CUSTOM_GROUPS_ADMIN', 'CUSTOM_GROUP_CREATOR', 'APPLICATIONS_ADMIN', 'APPLICATIONS_CREATOR', 'CREDENTIALS_ADMIN', 'CREDENTIALS_CREATOR', 'CONVERSATIONS_ADMIN', 'CONVERSATIONS_CREATOR', 'AUTONOMOUS_AGENTS_ADMIN', 'AUTONOMOUS_AGENTS_CREATOR', 'DEVELOPMENT_PLATFORMS_ADMIN', 'DEVELOPMENT_PLATFORMS_CREATOR')"
    )
