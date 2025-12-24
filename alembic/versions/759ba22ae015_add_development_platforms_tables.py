"""add_development_platforms_tables

Revision ID: 759ba22ae015
Revises: f2e8f73691da
Create Date: 2025-12-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '759ba22ae015'
down_revision: Union[str, Sequence[str], None] = 'c4262d1a8a76'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add development_platforms and development_platform_members tables."""
    
    # Create development_platforms table
    op.create_table(
        'development_platforms',
        sa.Column('id', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.String(length=2000), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('updated_by', sa.String(length=50), nullable=True),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('type', sa.String(length=255), nullable=True),
        sa.Column('iframe_url', sa.String(length=2000), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_development_platforms_tenant', 'development_platforms', ['tenant_id'])
    
    # Create development_platform_members table
    op.create_table(
        'development_platform_members',
        sa.Column('id', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('updated_by', sa.String(length=50), nullable=True),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('development_platform_id', sa.String(length=36), nullable=False),
        sa.Column('principal_id', sa.String(length=50), nullable=False),
        sa.Column('principal_type', sa.Enum(
            'IDENTITY_USER', 
            'IDENTITY_GROUP', 
            'CUSTOM_GROUP', 
            name='principal_type', 
            native_enum=False, 
            create_constraint=True, 
            validate_strings=True
        ), nullable=False),
        sa.Column('role', sa.Enum(
            'READ', 
            'WRITE', 
            'ADMIN', 
            name='permission_action', 
            native_enum=False, 
            create_constraint=True, 
            validate_strings=True
        ), nullable=False),
        sa.ForeignKeyConstraint(['development_platform_id'], ['development_platforms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('development_platform_id', 'principal_id', 'principal_type', name='uq_development_platform_members')
    )
    op.create_index('ix_dpm_development_platform', 'development_platform_members', ['development_platform_id'])
    op.create_index('ix_dpm_principal', 'development_platform_members', ['principal_id'])
    
    # Update tenant_role enum to include new development platform permissions
    # This is needed for the TenantPermissionEnum check constraint
    # Note: We use Enum with native_enum=False so we can extend the check constraint
    op.execute("""
        ALTER TABLE tenant_member_roles 
        DROP CONSTRAINT IF EXISTS tenant_role;
    """)
    
    # Re-add check constraint with additional values
    op.execute("""
        ALTER TABLE tenant_member_roles 
        ADD CONSTRAINT tenant_role 
        CHECK (role IN (
            'GLOBAL_ADMIN', 
            'READER', 
            'APPLICATIONS_ADMIN', 
            'APPLICATIONS_CREATOR',
            'CONVERSATIONS_ADMIN', 
            'CONVERSATIONS_CREATOR',
            'AUTONOMOUS_AGENTS_ADMIN', 
            'AUTONOMOUS_AGENTS_CREATOR',
            'CREDENTIALS_ADMIN', 
            'CREDENTIALS_CREATOR',
            'CUSTOM_GROUPS_ADMIN',
            'CUSTOM_GROUP_CREATOR',
            'DEVELOPMENT_PLATFORMS_ADMIN',
            'DEVELOPMENT_PLATFORMS_CREATOR'
        ));
    """)


def downgrade() -> None:
    """Remove development_platforms and development_platform_members tables."""
    
    # Drop development_platform_members table
    op.drop_index('ix_dpm_principal', table_name='development_platform_members')
    op.drop_index('ix_dpm_development_platform', table_name='development_platform_members')
    op.drop_table('development_platform_members')
    
    # Drop development_platforms table
    op.drop_index('ix_development_platforms_tenant', table_name='development_platforms')
    op.drop_table('development_platforms')
    
    # Revert tenant_role check constraint to exclude development platform permissions
    op.execute("""
        ALTER TABLE tenant_member_roles 
        DROP CONSTRAINT IF EXISTS tenant_role;
    """)
    
    op.execute("""
        ALTER TABLE tenant_member_roles 
        ADD CONSTRAINT tenant_role 
        CHECK (role IN (
            'GLOBAL_ADMIN', 
            'READER', 
            'APPLICATIONS_ADMIN', 
            'APPLICATIONS_CREATOR',
            'CONVERSATIONS_ADMIN', 
            'CONVERSATIONS_CREATOR',
            'AUTONOMOUS_AGENTS_ADMIN', 
            'AUTONOMOUS_AGENTS_CREATOR',
            'CREDENTIALS_ADMIN', 
            'CREDENTIALS_CREATOR',
            'CUSTOM_GROUPS_ADMIN',
            'CUSTOM_GROUP_CREATOR'
        ));
    """)
