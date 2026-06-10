"""add observability tables: message_metrics, message_feedback, audit_logs

Revision ID: a1b2c3d4e5f6
Revises: 96a9b99a62df
Create Date: 2026-04-22 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from unifiedui.core.database.models import HighPrecisionDateTime, PortableJSON

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "96a9b99a62df"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chat_agent_id"], ["chat_agents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
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

    op.create_table(
        "message_feedback",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("message_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.String(length=50), nullable=False),
        sa.Column(
            "rating",
            sa.Enum("THUMBS_UP", "THUMBS_DOWN", name="message_feedback_rating", native_enum=False),
            nullable=False,
        ),
        sa.Column("reasons", PortableJSON, nullable=False),
        sa.Column("comment", sa.String(length=4000), nullable=True),
        sa.Column("created_at", HighPrecisionDateTime(), nullable=False),
        sa.Column("updated_at", HighPrecisionDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "message_id", "user_id", name="uq_message_feedback_per_user"),
    )
    op.create_index("ix_message_feedback_message", "message_feedback", ["tenant_id", "message_id"])
    op.create_index("ix_message_feedback_conversation", "message_feedback", ["tenant_id", "conversation_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("timestamp", HighPrecisionDateTime(), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=True),
        sa.Column("actor_email", sa.String(length=255), nullable=True),
        sa.Column(
            "action",
            sa.Enum(
                "CREATE",
                "UPDATE",
                "DELETE",
                "MEMBER_ADD",
                "MEMBER_REMOVE",
                "ROLE_CHANGE",
                "EXECUTE",
                name="audit_action",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "resource_type",
            sa.Enum(
                "CHAT_AGENT",
                "WORKFLOW",
                "CREDENTIAL",
                "TOOL",
                "TAG",
                "PRINCIPAL",
                "CUSTOM_GROUP",
                "AI_MODEL",
                "EXTERNAL_APP",
                "TENANT_SETTING",
                name="audit_resource_type",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("resource_id", sa.String(length=36), nullable=False),
        sa.Column("resource_name", sa.String(length=255), nullable=True),
        sa.Column("changes", PortableJSON, nullable=True),
        sa.Column("client_ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_tenant_time", "audit_logs", ["tenant_id", "timestamp"])
    op.create_index(
        "ix_audit_logs_tenant_resource", "audit_logs", ["tenant_id", "resource_type", "resource_id"]
    )
    op.create_index("ix_audit_logs_tenant_actor", "audit_logs", ["tenant_id", "actor_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_tenant_actor", table_name="audit_logs")
    op.drop_index("ix_audit_logs_tenant_resource", table_name="audit_logs")
    op.drop_index("ix_audit_logs_tenant_time", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_message_feedback_conversation", table_name="message_feedback")
    op.drop_index("ix_message_feedback_message", table_name="message_feedback")
    op.drop_table("message_feedback")

    op.drop_index("ix_message_metrics_tenant_workflow_time", table_name="message_metrics")
    op.drop_index("ix_message_metrics_tenant_agent_time", table_name="message_metrics")
    op.drop_index("ix_message_metrics_tenant_time", table_name="message_metrics")
    op.drop_index("ix_message_metrics_message_id", table_name="message_metrics")
    op.drop_table("message_metrics")
