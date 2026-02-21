"""add organization tables and extend tenant model

Revision ID: 001_add_organizations
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_add_organizations"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create organizations table
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("identity_provider", sa.String(50), nullable=False),
        sa.Column("identity_tenant_id", sa.String(255), nullable=False),
        sa.Column("subscription_tier", sa.String(50), nullable=False, server_default="free"),
        sa.Column("max_tenants", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("max_users", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.UniqueConstraint("identity_provider", "identity_tenant_id", name="uq_org_idp"),
    )
    op.create_index("ix_org_slug", "organizations", ["slug"])
    op.create_index("ix_org_idp", "organizations", ["identity_provider", "identity_tenant_id"])

    # Create organization_members table
    op.create_table(
        "organization_members",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("principal_id", sa.String(50), nullable=False),
        sa.Column(
            "principal_type",
            sa.String(50),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.String(50),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.UniqueConstraint("organization_id", "principal_id", "role", name="uq_org_member"),
    )
    op.create_index("ix_org_member_org", "organization_members", ["organization_id"])
    op.create_index("ix_org_member_principal", "organization_members", ["principal_id"])

    # Extend tenants table with new columns
    op.add_column(
        "tenants",
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "environment_type",
            sa.String(50),
            nullable=False,
            server_default="SANDBOX",
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "previous_stage_id",
            sa.String(36),
            sa.ForeignKey("tenants.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "tenants",
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "tenants",
        sa.Column("can_be_deleted", sa.Boolean(), nullable=False, server_default="true"),
    )


def downgrade() -> None:
    # Remove new tenant columns
    op.drop_column("tenants", "can_be_deleted")
    op.drop_column("tenants", "is_default")
    op.drop_column("tenants", "previous_stage_id")
    op.drop_column("tenants", "environment_type")
    op.drop_column("tenants", "organization_id")

    # Drop organization_members table
    op.drop_index("ix_org_member_principal", table_name="organization_members")
    op.drop_index("ix_org_member_org", table_name="organization_members")
    op.drop_table("organization_members")

    # Drop organizations table
    op.drop_index("ix_org_idp", table_name="organizations")
    op.drop_index("ix_org_slug", table_name="organizations")
    op.drop_table("organizations")
