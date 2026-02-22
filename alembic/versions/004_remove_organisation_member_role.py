"""004_remove_organisation_member_role

Revision ID: b4e8c3d2e567
Revises: a3f9b2c1d456
Create Date: 2026-02-22 19:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4e8c3d2e567"
down_revision: Union[str, Sequence[str], None] = "a3f9b2c1d456"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_ROLES = (
    "ORGANISATION_GLOBAL_ADMIN",
    "ORGANISATION_ADMIN",
    "ORGANISATION_TENANT_ADMIN",
    "ORGANISATION_TENANT_CREATOR",
    "ORGANISATION_MEMBER",
)

NEW_ROLES = (
    "ORGANISATION_GLOBAL_ADMIN",
    "ORGANISATION_ADMIN",
    "ORGANISATION_TENANT_ADMIN",
    "ORGANISATION_TENANT_CREATOR",
)


def upgrade() -> None:
    """Remove ORGANISATION_MEMBER role from organization_members table."""
    # Delete any existing rows with the ORGANISATION_MEMBER role
    op.execute(
        "DELETE FROM organization_members WHERE role = 'ORGANISATION_MEMBER'"
    )

    # Recreate the check constraint without ORGANISATION_MEMBER
    # For non-native enums, SQLAlchemy uses a CHECK constraint
    op.drop_constraint(
        "organization_role",
        "organization_members",
        type_="check",
    )

    new_constraint = "role IN ({})".format(
        ", ".join(f"'{r}'" for r in NEW_ROLES)
    )
    op.create_check_constraint(
        "organization_role",
        "organization_members",
        sa.text(new_constraint),
    )


def downgrade() -> None:
    """Re-add ORGANISATION_MEMBER role to the check constraint."""
    op.drop_constraint(
        "organization_role",
        "organization_members",
        type_="check",
    )

    old_constraint = "role IN ({})".format(
        ", ".join(f"'{r}'" for r in OLD_ROLES)
    )
    op.create_check_constraint(
        "organization_role",
        "organization_members",
        sa.text(old_constraint),
    )
