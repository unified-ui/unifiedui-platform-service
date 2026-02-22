"""005_rename_global_admin_remove_org_admin

Revision ID: c5f9d3e4f678
Revises: b4e8c3d2e567
Create Date: 2026-02-22 20:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c5f9d3e4f678"
down_revision: Union[str, Sequence[str], None] = "b4e8c3d2e567"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_TENANT_ROLES = (
    "READER",
    "GLOBAL_ADMIN",
    "CUSTOM_GROUPS_ADMIN",
    "CUSTOM_GROUP_CREATOR",
    "CHAT_AGENTS_ADMIN",
    "CHAT_AGENTS_CREATOR",
    "CREDENTIALS_ADMIN",
    "CREDENTIALS_CREATOR",
    "CONVERSATIONS_ADMIN",
    "CONVERSATIONS_CREATOR",
    "AUTONOMOUS_AGENTS_ADMIN",
    "AUTONOMOUS_AGENTS_CREATOR",
    "CHAT_WIDGETS_ADMIN",
    "CHAT_WIDGETS_CREATOR",
    "REACT_AGENT_ADMIN",
    "REACT_AGENT_CREATOR",
    "TENANT_AI_MODELS_ADMIN",
)

NEW_TENANT_ROLES = (
    "READER",
    "TENANT_GLOBAL_ADMIN",
    "CUSTOM_GROUPS_ADMIN",
    "CUSTOM_GROUP_CREATOR",
    "CHAT_AGENTS_ADMIN",
    "CHAT_AGENTS_CREATOR",
    "CREDENTIALS_ADMIN",
    "CREDENTIALS_CREATOR",
    "CONVERSATIONS_ADMIN",
    "CONVERSATIONS_CREATOR",
    "AUTONOMOUS_AGENTS_ADMIN",
    "AUTONOMOUS_AGENTS_CREATOR",
    "CHAT_WIDGETS_ADMIN",
    "CHAT_WIDGETS_CREATOR",
    "REACT_AGENT_ADMIN",
    "REACT_AGENT_CREATOR",
    "TENANT_AI_MODELS_ADMIN",
)

OLD_ORG_ROLES = (
    "ORGANISATION_GLOBAL_ADMIN",
    "ORGANISATION_ADMIN",
    "ORGANISATION_TENANT_ADMIN",
    "ORGANISATION_TENANT_CREATOR",
)

NEW_ORG_ROLES = (
    "ORGANISATION_GLOBAL_ADMIN",
    "ORGANISATION_TENANT_ADMIN",
    "ORGANISATION_TENANT_CREATOR",
)


def upgrade() -> None:
    """Rename GLOBAL_ADMIN to TENANT_GLOBAL_ADMIN in tenant_members.

    Remove ORGANISATION_ADMIN from organization_members.
    """
    op.execute(
        "UPDATE tenant_members SET role = 'TENANT_GLOBAL_ADMIN' WHERE role = 'GLOBAL_ADMIN'"
    )

    op.drop_constraint(
        "tenant_role",
        "tenant_members",
        type_="check",
    )
    new_tenant_constraint = "role IN ({})".format(
        ", ".join(f"'{r}'" for r in NEW_TENANT_ROLES)
    )
    op.create_check_constraint(
        "tenant_role",
        "tenant_members",
        sa.text(new_tenant_constraint),
    )

    op.execute(
        "DELETE FROM organization_members WHERE role = 'ORGANISATION_ADMIN'"
    )

    op.drop_constraint(
        "organization_role",
        "organization_members",
        type_="check",
    )
    new_org_constraint = "role IN ({})".format(
        ", ".join(f"'{r}'" for r in NEW_ORG_ROLES)
    )
    op.create_check_constraint(
        "organization_role",
        "organization_members",
        sa.text(new_org_constraint),
    )


def downgrade() -> None:
    """Revert TENANT_GLOBAL_ADMIN back to GLOBAL_ADMIN. Re-add ORGANISATION_ADMIN."""
    op.execute(
        "UPDATE tenant_members SET role = 'GLOBAL_ADMIN' WHERE role = 'TENANT_GLOBAL_ADMIN'"
    )

    op.drop_constraint(
        "tenant_role",
        "tenant_members",
        type_="check",
    )
    old_tenant_constraint = "role IN ({})".format(
        ", ".join(f"'{r}'" for r in OLD_TENANT_ROLES)
    )
    op.create_check_constraint(
        "tenant_role",
        "tenant_members",
        sa.text(old_tenant_constraint),
    )

    op.drop_constraint(
        "organization_role",
        "organization_members",
        type_="check",
    )
    old_org_constraint = "role IN ({})".format(
        ", ".join(f"'{r}'" for r in OLD_ORG_ROLES)
    )
    op.create_check_constraint(
        "organization_role",
        "organization_members",
        sa.text(old_org_constraint),
    )
