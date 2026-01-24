"""add_tools_table

Revision ID: g1a2b3c4d5e6
Revises: e68a779863bf
Create Date: 2025-01-25 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'g1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e68a779863bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Create tools, tool_members, and tool_tags tables."""
    
    # Create tools table
    op.create_table('tools',
        sa.Column('id', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.String(length=2000), nullable=True),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),  # MCP_SERVER, OPENAPI_DEFINITION
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('credential_id', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('updated_by', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('tools_pkey')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('tools_tenant_id_fkey'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['credential_id'], ['credentials.id'], name=op.f('tools_credential_id_fkey'), ondelete='SET NULL'),
        sa.CheckConstraint("type IN ('MCP_SERVER', 'OPENAPI_DEFINITION')", name=op.f('tool_type_check'))
    )
    op.create_index(op.f('ix_tools_tenant'), 'tools', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_tools_credential'), 'tools', ['credential_id'], unique=False)
    
    # Create tool_members table
    op.create_table('tool_members',
        sa.Column('id', sa.String(length=100), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('tool_id', sa.String(length=100), nullable=False),
        sa.Column('principal_id', sa.String(length=50), nullable=False),
        sa.Column('role', sa.String(length=5), nullable=False),  # READ, WRITE, ADMIN
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('updated_by', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('tool_members_pkey')),
        sa.ForeignKeyConstraint(['tool_id'], ['tools.id'], name=op.f('tool_members_tool_id_fkey'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'principal_id'], 
            ['principals.tenant_id', 'principals.principal_id'], 
            name=op.f('fk_tool_members_principal'), 
            ondelete='CASCADE'
        ),
        sa.UniqueConstraint('tool_id', 'principal_id', name=op.f('uq_tool_members')),
        sa.CheckConstraint("role IN ('READ', 'WRITE', 'ADMIN')", name=op.f('tool_permission_action_check'))
    )
    op.create_index(op.f('ix_tool_members_tool'), 'tool_members', ['tool_id'], unique=False)
    op.create_index(op.f('ix_tool_members_principal'), 'tool_members', ['principal_id'], unique=False)
    
    # Create tool_tags table
    op.create_table('tool_tags',
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.Column('tool_id', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('updated_by', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('tenant_id', 'tag_id', 'tool_id', name=op.f('tool_tags_pkey')),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], name=op.f('tool_tags_tag_id_fkey'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tool_id'], ['tools.id'], name=op.f('tool_tags_tool_id_fkey'), ondelete='CASCADE')
    )
    op.create_index(op.f('ix_tool_tags_tag'), 'tool_tags', ['tag_id'], unique=False)
    op.create_index(op.f('ix_tool_tags_tool'), 'tool_tags', ['tool_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema - Remove tools, tool_members, and tool_tags tables."""
    
    # Drop tool_tags first (depends on tools and tags)
    op.drop_index(op.f('ix_tool_tags_tool'), table_name='tool_tags')
    op.drop_index(op.f('ix_tool_tags_tag'), table_name='tool_tags')
    op.drop_table('tool_tags')
    
    # Drop tool_members (depends on tools and principals)
    op.drop_index(op.f('ix_tool_members_principal'), table_name='tool_members')
    op.drop_index(op.f('ix_tool_members_tool'), table_name='tool_members')
    op.drop_table('tool_members')
    
    # Drop tools table
    op.drop_index(op.f('ix_tools_credential'), table_name='tools')
    op.drop_index(op.f('ix_tools_tenant'), table_name='tools')
    op.drop_table('tools')
