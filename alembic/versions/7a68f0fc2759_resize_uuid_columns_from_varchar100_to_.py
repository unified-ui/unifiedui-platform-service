"""resize uuid columns from varchar100 to varchar36

Revision ID: 7a68f0fc2759
Revises: 2dcb01103929
Create Date: 2026-02-08 00:41:36.612289

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a68f0fc2759'
down_revision: Union[str, Sequence[str], None] = '2dcb01103929'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('tenants', 'id',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=36),
               existing_nullable=False)
    op.alter_column('tenant_members', 'id',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=36),
               existing_nullable=False)
    op.alter_column('custom_group_members', 'id',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=36),
               existing_nullable=False)
    op.alter_column('applications', 'id',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=36),
               existing_nullable=False)
    op.alter_column('application_members', 'id',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=36),
               existing_nullable=False)
    op.alter_column('application_tags', 'application_id',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=36),
               existing_nullable=False)
    op.alter_column('application_user_favorites', 'application_id',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=36),
               existing_nullable=False)
    op.alter_column('conversations', 'id',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=36),
               existing_nullable=False)
    op.alter_column('conversations', 'application_id',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=36),
               existing_nullable=False)
    op.alter_column('conversation_members', 'id',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=36),
               existing_nullable=False)
    op.alter_column('conversation_user_favorites', 'conversation_id',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=36),
               existing_nullable=False)
    op.alter_column('autonomous_agents', 'id',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=36),
               existing_nullable=False)
    op.alter_column('autonomous_agent_members', 'id',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=36),
               existing_nullable=False)
    op.alter_column('autonomous_agent_tags', 'autonomous_agent_id',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=36),
               existing_nullable=False)
    op.alter_column('autonomous_agent_user_favorites', 'autonomous_agent_id',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=36),
               existing_nullable=False)
    op.alter_column('credentials', 'id',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=36),
               existing_nullable=False)
    op.alter_column('credential_members', 'id',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=36),
               existing_nullable=False)
    op.alter_column('credential_tags', 'credential_id',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=36),
               existing_nullable=False)
    op.alter_column('chat_widgets', 'id',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=36),
               existing_nullable=False)
    op.alter_column('chat_widget_members', 'id',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=36),
               existing_nullable=False)
    op.alter_column('chat_widget_tags', 'chat_widget_id',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=36),
               existing_nullable=False)
    op.alter_column('tools', 'id',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=36),
               existing_nullable=False)
    op.alter_column('tools', 'credential_id',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=36),
               existing_nullable=True)
    op.alter_column('tool_members', 'id',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=36),
               existing_nullable=False)
    op.alter_column('tool_members', 'tool_id',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=36),
               existing_nullable=False)
    op.alter_column('tool_tags', 'tool_id',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=36),
               existing_nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('tool_tags', 'tool_id',
               existing_type=sa.String(length=36),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
    op.alter_column('tool_members', 'tool_id',
               existing_type=sa.String(length=36),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
    op.alter_column('tool_members', 'id',
               existing_type=sa.String(length=36),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
    op.alter_column('tools', 'credential_id',
               existing_type=sa.String(length=36),
               type_=sa.VARCHAR(length=100),
               existing_nullable=True)
    op.alter_column('tools', 'id',
               existing_type=sa.String(length=36),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
    op.alter_column('chat_widget_tags', 'chat_widget_id',
               existing_type=sa.String(length=36),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
    op.alter_column('chat_widget_members', 'id',
               existing_type=sa.String(length=36),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
    op.alter_column('chat_widgets', 'id',
               existing_type=sa.String(length=36),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
    op.alter_column('credential_tags', 'credential_id',
               existing_type=sa.String(length=36),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
    op.alter_column('credential_members', 'id',
               existing_type=sa.String(length=36),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
    op.alter_column('credentials', 'id',
               existing_type=sa.String(length=36),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
    op.alter_column('autonomous_agent_user_favorites', 'autonomous_agent_id',
               existing_type=sa.String(length=36),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
    op.alter_column('autonomous_agent_tags', 'autonomous_agent_id',
               existing_type=sa.String(length=36),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
    op.alter_column('autonomous_agent_members', 'id',
               existing_type=sa.String(length=36),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
    op.alter_column('autonomous_agents', 'id',
               existing_type=sa.String(length=36),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
    op.alter_column('conversation_user_favorites', 'conversation_id',
               existing_type=sa.String(length=36),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
    op.alter_column('conversation_members', 'id',
               existing_type=sa.String(length=36),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
    op.alter_column('conversations', 'application_id',
               existing_type=sa.String(length=36),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
    op.alter_column('conversations', 'id',
               existing_type=sa.String(length=36),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
    op.alter_column('application_user_favorites', 'application_id',
               existing_type=sa.String(length=36),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
    op.alter_column('application_tags', 'application_id',
               existing_type=sa.String(length=36),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
    op.alter_column('application_members', 'id',
               existing_type=sa.String(length=36),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
    op.alter_column('applications', 'id',
               existing_type=sa.String(length=36),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
    op.alter_column('custom_group_members', 'id',
               existing_type=sa.String(length=36),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
    op.alter_column('tenant_members', 'id',
               existing_type=sa.String(length=36),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
    op.alter_column('tenants', 'id',
               existing_type=sa.String(length=36),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
