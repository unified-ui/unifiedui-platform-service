"""remove_is_active_and_change_defaults

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-25 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove is_active from workflows, chat_widgets, conversations, tenant_ai_models.

    Change default of is_active from False to True for chat_agents and credentials.
    """
    op.drop_column("workflows", "is_active")
    op.drop_column("chat_widgets", "is_active")
    op.drop_column("conversations", "is_active")
    op.drop_column("tenant_ai_models", "is_active")

    op.alter_column(
        "chat_agents",
        "is_active",
        server_default=sa.text("true"),
        existing_type=sa.Boolean(),
        existing_nullable=False,
    )
    op.alter_column(
        "credentials",
        "is_active",
        server_default=sa.text("true"),
        existing_type=sa.Boolean(),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Re-add is_active columns and revert defaults."""
    op.add_column(
        "workflows",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "chat_widgets",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "conversations",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "tenant_ai_models",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.alter_column(
        "chat_agents",
        "is_active",
        server_default=sa.text("false"),
        existing_type=sa.Boolean(),
        existing_nullable=False,
    )
    op.alter_column(
        "credentials",
        "is_active",
        server_default=sa.text("false"),
        existing_type=sa.Boolean(),
        existing_nullable=False,
    )
