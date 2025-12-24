"""add_tags_and_junction_tables

Revision ID: c9d8e7f6a5b4
Revises: b5f2a9c8d3e7
Create Date: 2025-01-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9d8e7f6a5b4'
down_revision: Union[str, None] = 'b5f2a9c8d3e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create sequence for tag IDs starting at 10000
    op.execute("CREATE SEQUENCE IF NOT EXISTS tag_id_seq START WITH 10000")
    
    # Create tags table
    op.create_table(
        'tags',
        sa.Column('id', sa.Integer(), sa.Sequence('tag_id_seq'), nullable=False, server_default=sa.text("nextval('tag_id_seq')")),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(50), nullable=True),
        sa.Column('updated_by', sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_tag_tenant_name')
    )
    op.create_index('ix_tags_tenant', 'tags', ['tenant_id'])
    op.create_index('ix_tags_name', 'tags', ['name'])
    
    # Create application_tags junction table
    op.create_table(
        'application_tags',
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('tag_id', sa.Integer(), sa.ForeignKey('tags.id', ondelete='CASCADE'), nullable=False),
        sa.Column('application_id', sa.String(100), sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=False),
        sa.PrimaryKeyConstraint('tenant_id', 'tag_id', 'application_id')
    )
    op.create_index('ix_at_application', 'application_tags', ['application_id'])
    op.create_index('ix_at_tag', 'application_tags', ['tag_id'])
    
    # Create autonomous_agent_tags junction table
    op.create_table(
        'autonomous_agent_tags',
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('tag_id', sa.Integer(), sa.ForeignKey('tags.id', ondelete='CASCADE'), nullable=False),
        sa.Column('autonomous_agent_id', sa.String(100), sa.ForeignKey('autonomous_agents.id', ondelete='CASCADE'), nullable=False),
        sa.PrimaryKeyConstraint('tenant_id', 'tag_id', 'autonomous_agent_id')
    )
    op.create_index('ix_aat_autonomous_agent', 'autonomous_agent_tags', ['autonomous_agent_id'])
    op.create_index('ix_aat_tag', 'autonomous_agent_tags', ['tag_id'])
    
    # Create chat_widget_tags junction table
    op.create_table(
        'chat_widget_tags',
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('tag_id', sa.Integer(), sa.ForeignKey('tags.id', ondelete='CASCADE'), nullable=False),
        sa.Column('chat_widget_id', sa.String(100), sa.ForeignKey('chat_widgets.id', ondelete='CASCADE'), nullable=False),
        sa.PrimaryKeyConstraint('tenant_id', 'tag_id', 'chat_widget_id')
    )
    op.create_index('ix_cwt_chat_widget', 'chat_widget_tags', ['chat_widget_id'])
    op.create_index('ix_cwt_tag', 'chat_widget_tags', ['tag_id'])
    
    # Create credential_tags junction table
    op.create_table(
        'credential_tags',
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('tag_id', sa.Integer(), sa.ForeignKey('tags.id', ondelete='CASCADE'), nullable=False),
        sa.Column('credential_id', sa.String(100), sa.ForeignKey('credentials.id', ondelete='CASCADE'), nullable=False),
        sa.PrimaryKeyConstraint('tenant_id', 'tag_id', 'credential_id')
    )
    op.create_index('ix_ct_credential', 'credential_tags', ['credential_id'])
    op.create_index('ix_ct_tag', 'credential_tags', ['tag_id'])
    
    # Create development_platform_tags junction table
    op.create_table(
        'development_platform_tags',
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('tag_id', sa.Integer(), sa.ForeignKey('tags.id', ondelete='CASCADE'), nullable=False),
        sa.Column('development_platform_id', sa.String(100), sa.ForeignKey('development_platforms.id', ondelete='CASCADE'), nullable=False),
        sa.PrimaryKeyConstraint('tenant_id', 'tag_id', 'development_platform_id')
    )
    op.create_index('ix_dpt_development_platform', 'development_platform_tags', ['development_platform_id'])
    op.create_index('ix_dpt_tag', 'development_platform_tags', ['tag_id'])


def downgrade() -> None:
    # Drop junction tables
    op.drop_table('development_platform_tags')
    op.drop_table('credential_tags')
    op.drop_table('chat_widget_tags')
    op.drop_table('autonomous_agent_tags')
    op.drop_table('application_tags')
    
    # Drop tags table
    op.drop_table('tags')
    
    # Drop sequence
    op.execute("DROP SEQUENCE IF EXISTS tag_id_seq")
