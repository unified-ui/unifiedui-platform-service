"""003_tenant_organization_id_non_nullable

Revision ID: a3f9b2c1d456
Revises: 7666a9c36796
Create Date: 2026-02-22 14:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a3f9b2c1d456"
down_revision: Union[str, Sequence[str], None] = "7666a9c36796"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make tenants.organization_id non-nullable."""
    op.alter_column(
        "tenants",
        "organization_id",
        existing_type=sa.String(36),
        nullable=False,
    )


def downgrade() -> None:
    """Revert tenants.organization_id back to nullable."""
    op.alter_column(
        "tenants",
        "organization_id",
        existing_type=sa.String(36),
        nullable=True,
    )
