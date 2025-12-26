"""Add custom_group_members table

Revision ID: a3f9c5d7e8b1
Revises: fb92d04935a0
Create Date: 2024-12-26 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f9c5d7e8b1'
down_revision: Union[str, None] = 'fb92d04935a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create custom_group_members table for tracking membership in custom groups."""
    op.create_table(
        'custom_group_members',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('custom_group_id', sa.String(50), nullable=False),
        sa.Column('principal_id', sa.String(50), nullable=False),
        sa.Column('role', sa.Enum('READ', 'WRITE', 'ADMIN', name='permissionactionenum'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_by', sa.String(50), nullable=True),
        sa.Column('updated_by', sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['tenant_id'],
            ['tenants.id'],
            ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'custom_group_id'],
            ['principals.tenant_id', 'principals.principal_id'],
            ondelete='CASCADE',
            name='fk_custom_group_members_custom_group'
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'principal_id'],
            ['principals.tenant_id', 'principals.principal_id'],
            ondelete='CASCADE',
            name='fk_custom_group_members_principal'
        ),
        sa.UniqueConstraint('tenant_id', 'custom_group_id', 'principal_id', name='uq_custom_group_members')
    )
    
    # Create indexes
    op.create_index('ix_cgm_tenant', 'custom_group_members', ['tenant_id'])
    op.create_index('ix_cgm_custom_group', 'custom_group_members', ['custom_group_id'])
    op.create_index('ix_cgm_principal', 'custom_group_members', ['principal_id'])


def downgrade() -> None:
    """Drop custom_group_members table."""
    op.drop_index('ix_cgm_principal', table_name='custom_group_members')
    op.drop_index('ix_cgm_custom_group', table_name='custom_group_members')
    op.drop_index('ix_cgm_tenant', table_name='custom_group_members')
    op.drop_table('custom_group_members')
