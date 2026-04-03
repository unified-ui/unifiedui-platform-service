"""Add external_app_user_favorites table.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-03 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create external_app_user_favorites table."""
    op.create_table(
        "external_app_user_favorites",
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(50), nullable=False),
        sa.Column("external_app_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.String(50), nullable=True),
        sa.Column("updated_by", sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_external_app_user_favorites_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["external_app_id"],
            ["external_apps.id"],
            name="fk_external_app_user_favorites_external_app",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["principals.tenant_id", "principals.principal_id"],
            name="fk_external_app_user_favorites_principal",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("tenant_id", "user_id", "external_app_id"),
    )

    op.create_index("ix_eauf_user", "external_app_user_favorites", ["user_id"])
    op.create_index("ix_eauf_external_app", "external_app_user_favorites", ["external_app_id"])


def downgrade() -> None:
    """Drop external_app_user_favorites table."""
    op.drop_index("ix_eauf_external_app", table_name="external_app_user_favorites")
    op.drop_index("ix_eauf_user", table_name="external_app_user_favorites")
    op.drop_table("external_app_user_favorites")
