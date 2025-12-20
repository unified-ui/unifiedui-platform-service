"""drop_and_recreate_member_tables_without_name_description

Revision ID: f2e8f73691da
Revises: e154058dadca
Create Date: 2025-12-20 19:56:14.439554

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2e8f73691da'
down_revision: Union[str, Sequence[str], None] = 'e154058dadca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema by dropping and recreating member tables without name/description fields."""
    
    # Drop all member tables in correct order (respecting foreign keys)
    # First drop tables that reference other member tables
    op.drop_table('tenant_member_roles')
    
    # Then drop all other member tables
    op.drop_table('application_members')
    op.drop_table('conversation_members')
    op.drop_table('autonomous_agent_members')
    op.drop_table('credential_members')
    op.drop_table('custom_group_members')
    op.drop_table('tenant_members')
    
    # Recreate tenant_members table without name/description
    op.create_table(
        'tenant_members',
        sa.Column('id', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('updated_by', sa.String(length=50), nullable=True),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('principal_id', sa.String(length=50), nullable=False),
        sa.Column('principal_type', sa.Enum('IDENTITY_USER', 'IDENTITY_GROUP', 'CUSTOM_GROUP', name='principal_type', native_enum=False, create_constraint=True, validate_strings=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'principal_id', 'principal_type', name='uq_tenant_members')
    )
    op.create_index('ix_tenant_members_tenant', 'tenant_members', ['tenant_id'])
    op.create_index('ix_tenant_members_principal', 'tenant_members', ['principal_id'])
    
    # Recreate tenant_member_roles table without name/description
    op.create_table(
        'tenant_member_roles',
        sa.Column('id', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('updated_by', sa.String(length=50), nullable=True),
        sa.Column('tenant_member_id', sa.String(length=36), nullable=False),
        sa.Column('role', sa.Enum('GLOBAL_ADMIN', 'READER', 'APPLICATIONS_ADMIN', 'CONVERSATIONS_ADMIN', 'AUTONOMOUS_AGENTS_ADMIN', 'CREDENTIALS_ADMIN', 'CUSTOM_GROUPS_ADMIN', name='tenant_role', native_enum=False, create_constraint=True, validate_strings=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_member_id'], ['tenant_members.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_member_id', 'role', name='uq_tenant_member_roles')
    )
    op.create_index('ix_tmr_tenant_member', 'tenant_member_roles', ['tenant_member_id'])
    
    # Recreate custom_group_members table without name/description
    op.create_table(
        'custom_group_members',
        sa.Column('id', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('updated_by', sa.String(length=50), nullable=True),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('custom_group_id', sa.String(length=36), nullable=False),
        sa.Column('principal_id', sa.String(length=50), nullable=False),
        sa.Column('principal_type', sa.Enum('IDENTITY_USER', 'IDENTITY_GROUP', 'CUSTOM_GROUP', name='principal_type', native_enum=False, create_constraint=True, validate_strings=True), nullable=False),
        sa.Column('role', sa.Enum('ADMIN', 'WRITE', 'READ', name='permission_action', native_enum=False, create_constraint=True, validate_strings=True), nullable=False),
        sa.ForeignKeyConstraint(['custom_group_id'], ['custom_groups.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('custom_group_id', 'principal_id', 'principal_type', name='uq_custom_group_members')
    )
    op.create_index('ix_cgm_custom_group', 'custom_group_members', ['custom_group_id'])
    op.create_index('ix_cgm_principal', 'custom_group_members', ['principal_id'])
    
    # Recreate application_members table without name/description
    op.create_table(
        'application_members',
        sa.Column('id', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('updated_by', sa.String(length=50), nullable=True),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('application_id', sa.String(length=36), nullable=False),
        sa.Column('principal_id', sa.String(length=50), nullable=False),
        sa.Column('principal_type', sa.Enum('IDENTITY_USER', 'IDENTITY_GROUP', 'CUSTOM_GROUP', name='principal_type', native_enum=False, create_constraint=True, validate_strings=True), nullable=False),
        sa.Column('role', sa.Enum('ADMIN', 'WRITE', 'READ', name='permission_action', native_enum=False, create_constraint=True, validate_strings=True), nullable=False),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('application_id', 'principal_id', 'principal_type', name='uq_application_members')
    )
    op.create_index('ix_am_application', 'application_members', ['application_id'])
    op.create_index('ix_am_principal', 'application_members', ['principal_id'])
    
    # Recreate conversation_members table without name/description
    op.create_table(
        'conversation_members',
        sa.Column('id', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('updated_by', sa.String(length=50), nullable=True),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('conversation_id', sa.String(length=36), nullable=False),
        sa.Column('principal_id', sa.String(length=50), nullable=False),
        sa.Column('principal_type', sa.Enum('IDENTITY_USER', 'IDENTITY_GROUP', 'CUSTOM_GROUP', name='principal_type', native_enum=False, create_constraint=True, validate_strings=True), nullable=False),
        sa.Column('role', sa.Enum('ADMIN', 'WRITE', 'READ', name='permission_action', native_enum=False, create_constraint=True, validate_strings=True), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('conversation_id', 'principal_id', 'principal_type', name='uq_conversation_members')
    )
    op.create_index('ix_cm_conversation', 'conversation_members', ['conversation_id'])
    op.create_index('ix_cm_principal', 'conversation_members', ['principal_id'])
    
    # Recreate autonomous_agent_members table without name/description
    op.create_table(
        'autonomous_agent_members',
        sa.Column('id', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('updated_by', sa.String(length=50), nullable=True),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('autonomous_agent_id', sa.String(length=36), nullable=False),
        sa.Column('principal_id', sa.String(length=50), nullable=False),
        sa.Column('principal_type', sa.Enum('IDENTITY_USER', 'IDENTITY_GROUP', 'CUSTOM_GROUP', name='principal_type', native_enum=False, create_constraint=True, validate_strings=True), nullable=False),
        sa.Column('role', sa.Enum('ADMIN', 'WRITE', 'READ', name='permission_action', native_enum=False, create_constraint=True, validate_strings=True), nullable=False),
        sa.ForeignKeyConstraint(['autonomous_agent_id'], ['autonomous_agents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('autonomous_agent_id', 'principal_id', 'principal_type', name='uq_autonomous_agent_members')
    )
    op.create_index('ix_aam_autonomous_agent', 'autonomous_agent_members', ['autonomous_agent_id'])
    op.create_index('ix_aam_principal', 'autonomous_agent_members', ['principal_id'])
    
    # Recreate credential_members table without name/description
    op.create_table(
        'credential_members',
        sa.Column('id', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('updated_by', sa.String(length=50), nullable=True),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('credential_id', sa.String(length=36), nullable=False),
        sa.Column('principal_id', sa.String(length=50), nullable=False),
        sa.Column('principal_type', sa.Enum('IDENTITY_USER', 'IDENTITY_GROUP', 'CUSTOM_GROUP', name='principal_type', native_enum=False, create_constraint=True, validate_strings=True), nullable=False),
        sa.Column('role', sa.Enum('ADMIN', 'WRITE', 'READ', name='permission_action', native_enum=False, create_constraint=True, validate_strings=True), nullable=False),
        sa.ForeignKeyConstraint(['credential_id'], ['credentials.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('credential_id', 'principal_id', 'principal_type', name='uq_credential_members')
    )
    op.create_index('ix_crm_credential', 'credential_members', ['credential_id'])
    op.create_index('ix_crm_principal', 'credential_members', ['principal_id'])


def downgrade() -> None:
    """Downgrade schema - not supported for this migration as data is lost."""
    raise NotImplementedError("Downgrade not supported - data has been dropped")
