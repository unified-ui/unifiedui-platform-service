"""drop message_metrics table

Message analytics are now computed from the agent-service MongoDB message
status fields. The message_metrics PostgreSQL table is no longer used.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2025-12-15 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from unifiedui.core.database.models import HighPrecisionDateTime

revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop the message_metrics table and its indexes."""
    op.drop_index("ix_message_metrics_tenant_workflow_time", table_name="message_metrics")
    op.drop_index("ix_message_metrics_tenant_agent_time", table_name="message_metrics")
    op.drop_index("ix_message_metrics_tenant_time", table_name="message_metrics")
    op.drop_index("ix_message_metrics_message_id", table_name="message_metrics")
    op.drop_table("message_metrics")
    op.execute("DROP TYPE IF EXISTS message_metric_status")


def downgrade() -> None:
    """Recreate message_metrics table."""
    op.create_table(
        "message_metrics",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("chat_agent_id", sa.String(length=36), nullable=True),
        sa.Column("workflow_id", sa.String(length=36), nullable=True),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("message_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.String(length=50), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("tokens_input", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_output", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("agent_type", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum("SUCCESS", "FAILED", "CANCELED", name="message_metric_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("created_at", HighPrecisionDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chat_agent_id"], ["chat_agents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("tenant_id", "message_id", name="uq_message_metrics_tenant_message"),
    )
    op.create_index("ix_message_metrics_message_id", "message_metrics", ["tenant_id", "message_id"])
    op.create_index("ix_message_metrics_tenant_time", "message_metrics", ["tenant_id", "created_at"])
    op.create_index(
        "ix_message_metrics_tenant_agent_time", "message_metrics", ["tenant_id", "chat_agent_id", "created_at"]
    )
    op.create_index(
        "ix_message_metrics_tenant_workflow_time", "message_metrics", ["tenant_id", "workflow_id", "created_at"]
    )
