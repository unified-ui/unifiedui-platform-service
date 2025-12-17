"""change_permission_to_enum

Revision ID: 93cdd1858cc1
Revises: 69010a7b316f
Create Date: 2025-12-17 13:31:02.505125

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '93cdd1858cc1'
down_revision: Union[str, Sequence[str], None] = '69010a7b316f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # The constraint already exists, just change the column type
    op.alter_column('tenant_member_permissions', 'permission',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.Enum('READER', 'GLOBAL_ADMIN', 'CUSTOM_GROUPS_ADMIN', 'APPLICATIONS_ADMIN', 'CREDENTIALS_ADMIN', 'AUTONOMOUS_AGENTS_ADMIN', name='tenant_role', native_enum=False, create_constraint=False),
               existing_nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Keep the constraint, just change column type back
    op.alter_column('tenant_member_permissions', 'permission',
               existing_type=sa.Enum('READER', 'GLOBAL_ADMIN', 'CUSTOM_GROUPS_ADMIN', 'APPLICATIONS_ADMIN', 'CREDENTIALS_ADMIN', 'AUTONOMOUS_AGENTS_ADMIN', name='tenant_role', native_enum=False, create_constraint=False),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
