"""Add is_active to principal and rename tenant_member_roles to tenant_members

Revision ID: f00f7482b184
Revises: a3f9c5d7e8b1
Create Date: 2026-01-02 09:58:24.159499

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f00f7482b184'
down_revision: Union[str, Sequence[str], None] = 'a3f9c5d7e8b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add is_active column to principals
    op.add_column('principals', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))
    
    # Rename tenant_member_roles to tenant_members
    op.rename_table('tenant_member_roles', 'tenant_members')
    
    # Rename indexes
    op.execute('ALTER INDEX ix_tmr_tenant RENAME TO ix_tm_tenant')
    op.execute('ALTER INDEX ix_tmr_principal RENAME TO ix_tm_principal')
    
    # Rename constraints
    op.execute('ALTER TABLE tenant_members RENAME CONSTRAINT tenant_member_roles_pkey TO tenant_members_pkey')
    op.execute('ALTER TABLE tenant_members RENAME CONSTRAINT uq_tenant_member_roles TO uq_tenant_members')
    op.execute('ALTER TABLE tenant_members RENAME CONSTRAINT fk_tenant_member_roles_principal TO fk_tenant_members_principal')
    op.execute('ALTER TABLE tenant_members RENAME CONSTRAINT tenant_member_roles_tenant_id_fkey TO tenant_members_tenant_id_fkey')


def downgrade() -> None:
    """Downgrade schema."""
    # Rename constraints back
    op.execute('ALTER TABLE tenant_members RENAME CONSTRAINT tenant_members_tenant_id_fkey TO tenant_member_roles_tenant_id_fkey')
    op.execute('ALTER TABLE tenant_members RENAME CONSTRAINT fk_tenant_members_principal TO fk_tenant_member_roles_principal')
    op.execute('ALTER TABLE tenant_members RENAME CONSTRAINT uq_tenant_members TO uq_tenant_member_roles')
    op.execute('ALTER TABLE tenant_members RENAME CONSTRAINT tenant_members_pkey TO tenant_member_roles_pkey')
    
    # Rename indexes back
    op.execute('ALTER INDEX ix_tm_principal RENAME TO ix_tmr_principal')
    op.execute('ALTER INDEX ix_tm_tenant RENAME TO ix_tmr_tenant')
    
    # Rename table back
    op.rename_table('tenant_members', 'tenant_member_roles')
    
    # Remove is_active column
    op.drop_column('principals', 'is_active')
