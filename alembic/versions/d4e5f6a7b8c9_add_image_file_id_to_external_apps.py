"""add image_file_id to external_apps

Revision ID: d4e5f6a7b8c9
Revises: c9d3e2f4a6b8
Create Date: 2026-03-22 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c9d3e2f4a6b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add image_file_id column to external_apps table."""
    op.add_column("external_apps", sa.Column("image_file_id", sa.String(36), nullable=True))


def downgrade() -> None:
    """Remove image_file_id column from external_apps table."""
    op.drop_column("external_apps", "image_file_id")
