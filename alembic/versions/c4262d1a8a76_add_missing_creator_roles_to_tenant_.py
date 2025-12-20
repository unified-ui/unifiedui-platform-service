"""add_missing_creator_roles_to_tenant_role_enum

Revision ID: c4262d1a8a76
Revises: f2e8f73691da
Create Date: 2025-12-20 22:52:47.988243

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4262d1a8a76'
down_revision: Union[str, Sequence[str], None] = 'f2e8f73691da'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add missing CREATOR roles to tenant_role enum constraint."""
    # For PostgreSQL, we need to update the CHECK constraint
    # Since we can't ALTER a CHECK constraint directly, we need to:
    # 1. Drop the old constraint
    # 2. Create a new one with all values
    
    # Get the constraint name from the table
    op.execute("""
        ALTER TABLE tenant_member_roles 
        DROP CONSTRAINT IF EXISTS tenant_role;
    """)
    
    # Recreate the constraint with all values including the missing CREATOR roles
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


def downgrade() -> None:
    """Remove CREATOR roles from tenant_role enum constraint."""
    # Drop the constraint with CREATOR roles
    op.execute("""
        ALTER TABLE tenant_member_roles 
        DROP CONSTRAINT IF EXISTS tenant_role;
    """)
    
    # Recreate the old constraint without CREATOR roles
    op.execute("""
        ALTER TABLE tenant_member_roles 
        ADD CONSTRAINT tenant_role 
        CHECK (role IN (
            'GLOBAL_ADMIN',
            'READER',
            'APPLICATIONS_ADMIN',
            'CONVERSATIONS_ADMIN',
            'AUTONOMOUS_AGENTS_ADMIN',
            'CREDENTIALS_ADMIN',
            'CUSTOM_GROUPS_ADMIN'
        ));
    """)
