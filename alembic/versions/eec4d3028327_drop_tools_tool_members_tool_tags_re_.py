"""drop_tools_tool_members_tool_tags_re_act_agent_versions_tables

Revision ID: eec4d3028327
Revises: c3d4e5f6a7b8
Create Date: 2026-05-23 12:13:06.563414

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'eec4d3028327'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop tool and ReACT agent version tables."""
    op.drop_table('tool_tags')
    op.drop_table('tool_members')
    op.drop_table('re_act_agent_versions')
    op.drop_table('tools')


def downgrade() -> None:
    """Recreate tool and ReACT agent version tables."""
    op.create_table(
        'tools',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_tools_tenant'), 'tools', ['tenant_id'])

    op.create_table(
        're_act_agent_versions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('agent_id', sa.String(length=36), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('security_prompt', sa.Text(), nullable=True),
        sa.Column('tool_use_prompt', sa.Text(), nullable=True),
        sa.Column('response_prompt', sa.Text(), nullable=True),
        sa.Column('tool_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('ai_model_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_by', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['chat_agents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('agent_id', 'version', name='uq_re_act_agent_versions_agent_version'),
    )
    op.create_index(op.f('ix_re_act_agent_versions_agent'), 're_act_agent_versions', ['agent_id'])
    op.create_index(op.f('ix_re_act_agent_versions_agent_version'), 're_act_agent_versions', ['agent_id', 'version'])

    op.create_table(
        'tool_members',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tool_id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('principal_id', sa.String(length=36), nullable=False),
        sa.Column('permission', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tool_id'], ['tools.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'principal_id'],
            ['principals.tenant_id', 'principals.principal_id'],
            name='fk_tool_members_principal',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tool_id', 'tenant_id', 'principal_id', name='uq_tool_members'),
    )
    op.create_index(op.f('ix_tool_members_tool'), 'tool_members', ['tool_id'])
    op.create_index(op.f('ix_tool_members_principal'), 'tool_members', ['tenant_id', 'principal_id'])

    op.create_table(
        'tool_tags',
        sa.Column('tool_id', sa.String(length=36), nullable=False),
        sa.Column('tag_id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(['tool_id'], ['tools.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('tool_id', 'tag_id'),
    )
    op.create_index(op.f('ix_tt_tool'), 'tool_tags', ['tool_id'])
    op.create_index(op.f('ix_tt_tag'), 'tool_tags', ['tag_id'])
