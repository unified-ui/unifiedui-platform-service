"""rename_tenant_roles_to_tenant_principals

Revision ID: 9023ab8ae861
Revises: aa47a1a1c134
Create Date: 2025-12-17 11:06:03.043500

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9023ab8ae861'
down_revision: Union[str, Sequence[str], None] = 'aa47a1a1c134'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Rename table
    op.rename_table('tenant_roles', 'tenant_principals')
    
    # Rename constraints (indexes and unique constraints are automatically renamed by PostgreSQL)
    # However, we need to explicitly rename the unique constraint
    op.drop_constraint('uq_tenant_roles', 'tenant_principals', type_='unique')
    op.create_unique_constraint(
        'uq_tenant_principals',
        'tenant_principals',
        ['tenant_id', 'principal_id', 'principal_type', 'role']
    )
    
    # Rename foreign key constraint
    op.drop_constraint('tenant_roles_tenant_id_fkey', 'tenant_principals', type_='foreignkey')
    op.create_foreign_key(
        'tenant_principals_tenant_id_fkey',
        'tenant_principals',
        'tenants',
        ['tenant_id'],
        ['id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Rename foreign key constraint back
    op.drop_constraint('tenant_principals_tenant_id_fkey', 'tenant_principals', type_='foreignkey')
    op.create_foreign_key(
        'tenant_roles_tenant_id_fkey',
        'tenant_principals',
        'tenants',
        ['tenant_id'],
        ['id']
    )
    
    # Rename unique constraint back
    op.drop_constraint('uq_tenant_principals', 'tenant_principals', type_='unique')
    op.create_unique_constraint(
        'uq_tenant_roles',
        'tenant_principals',
        ['tenant_id', 'principal_id', 'principal_type', 'role']
    )
    
    # Rename table back
    op.rename_table('tenant_principals', 'tenant_roles')
