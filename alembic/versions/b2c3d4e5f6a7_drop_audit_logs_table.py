"""drop audit_logs table

Audit events are now emitted as structured log records on the
``unifiedui.audit`` logger and forwarded to Azure Log Analytics.
The persistent audit_logs table is no longer used.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2025-12-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from unifiedui.core.database.models import HighPrecisionDateTime, PortableJSON

revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_audit_logs_tenant_actor", table_name="audit_logs")
    op.drop_index("ix_audit_logs_tenant_resource", table_name="audit_logs")
    op.drop_index("ix_audit_logs_tenant_time", table_name="audit_logs")
    op.drop_table("audit_logs")


def downgrade() -> None:
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
    op.create_index("ix_audit_logs_tenant_resource", "audit_logs", ["tenant_id", "resource_type", "resource_id"])
    op.create_index("ix_audit_logs_tenant_actor", "audit_logs", ["tenant_id", "actor_id"])
