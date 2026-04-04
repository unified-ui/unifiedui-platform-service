"""Rename autonomous_agents to workflows.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-04 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Rename autonomous_agents tables and related objects to workflows."""
    # ============================================================
    # 1. Drop indexes before renaming tables
    # ============================================================

    # autonomous_agents table indexes
    op.drop_index("ix_autonomous_agents_tenant", table_name="autonomous_agents", schema="unifiedui")

    # autonomous_agent_members table indexes
    op.drop_index("ix_aam_autonomous_agent", table_name="autonomous_agent_members", schema="unifiedui")
    op.drop_index("ix_aam_principal", table_name="autonomous_agent_members", schema="unifiedui")

    # autonomous_agent_tags table indexes
    op.drop_index("ix_aat_autonomous_agent", table_name="autonomous_agent_tags", schema="unifiedui")
    op.drop_index("ix_aat_tag", table_name="autonomous_agent_tags", schema="unifiedui")

    # autonomous_agent_user_favorites table indexes
    op.drop_index("ix_aauf_user", table_name="autonomous_agent_user_favorites", schema="unifiedui")
    op.drop_index("ix_aauf_autonomous_agent", table_name="autonomous_agent_user_favorites", schema="unifiedui")

    # ============================================================
    # 2. Drop constraints before renaming tables
    # ============================================================

    # autonomous_agents constraints
    op.drop_constraint("uq_autonomous_agent_tenant_name", "autonomous_agents", schema="unifiedui", type_="unique")

    # autonomous_agent_members constraints
    op.drop_constraint(
        "fk_autonomous_agent_members_principal", "autonomous_agent_members", schema="unifiedui", type_="foreignkey"
    )
    op.drop_constraint("uq_autonomous_agent_members", "autonomous_agent_members", schema="unifiedui", type_="unique")

    # autonomous_agent_user_favorites constraints
    op.drop_constraint(
        "fk_autonomous_agent_user_favorites_principal",
        "autonomous_agent_user_favorites",
        schema="unifiedui",
        type_="foreignkey",
    )

    # ============================================================
    # 3. Rename tables
    # ============================================================
    op.rename_table("autonomous_agents", "workflows", schema="unifiedui")
    op.rename_table("autonomous_agent_members", "workflow_members", schema="unifiedui")
    op.rename_table("autonomous_agent_tags", "workflow_tags", schema="unifiedui")
    op.rename_table("autonomous_agent_user_favorites", "workflow_user_favorites", schema="unifiedui")

    # ============================================================
    # 4. Rename columns
    # ============================================================

    # workflow_members: autonomous_agent_id -> workflow_id
    op.alter_column(
        "workflow_members",
        "autonomous_agent_id",
        new_column_name="workflow_id",
        schema="unifiedui",
    )

    # workflow_tags: autonomous_agent_id -> workflow_id
    op.alter_column(
        "workflow_tags",
        "autonomous_agent_id",
        new_column_name="workflow_id",
        schema="unifiedui",
    )

    # workflow_user_favorites: autonomous_agent_id -> workflow_id
    op.alter_column(
        "workflow_user_favorites",
        "autonomous_agent_id",
        new_column_name="workflow_id",
        schema="unifiedui",
    )

    # ============================================================
    # 5. Recreate constraints with new names
    # ============================================================

    # workflows constraints
    op.create_unique_constraint("uq_workflow_tenant_name", "workflows", ["tenant_id", "name"], schema="unifiedui")

    # workflow_members constraints
    op.create_foreign_key(
        "fk_workflow_members_principal",
        "workflow_members",
        "principals",
        ["tenant_id", "principal_id"],
        ["tenant_id", "principal_id"],
        source_schema="unifiedui",
        referent_schema="unifiedui",
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_workflow_members", "workflow_members", ["workflow_id", "principal_id"], schema="unifiedui"
    )

    # workflow_user_favorites constraints
    op.create_foreign_key(
        "fk_workflow_user_favorites_principal",
        "workflow_user_favorites",
        "principals",
        ["tenant_id", "user_id"],
        ["tenant_id", "principal_id"],
        source_schema="unifiedui",
        referent_schema="unifiedui",
        ondelete="CASCADE",
    )

    # ============================================================
    # 6. Recreate indexes with new names
    # ============================================================

    # workflows indexes
    op.create_index("ix_workflows_tenant", "workflows", ["tenant_id"], schema="unifiedui")

    # workflow_members indexes
    op.create_index("ix_wm_workflow", "workflow_members", ["workflow_id"], schema="unifiedui")
    op.create_index("ix_wm_principal", "workflow_members", ["principal_id"], schema="unifiedui")

    # workflow_tags indexes
    op.create_index("ix_wt_workflow", "workflow_tags", ["workflow_id"], schema="unifiedui")
    op.create_index("ix_wt_tag", "workflow_tags", ["tag_id"], schema="unifiedui")

    # workflow_user_favorites indexes
    op.create_index("ix_wuf_user", "workflow_user_favorites", ["user_id"], schema="unifiedui")
    op.create_index("ix_wuf_workflow", "workflow_user_favorites", ["workflow_id"], schema="unifiedui")

    # ============================================================
    # 7. Update TenantRoles enum values in tenant_members table
    # ============================================================
    op.execute(
        """
        UPDATE unifiedui.tenant_members
        SET role = 'WORKFLOWS_ADMIN'
        WHERE role = 'AUTONOMOUS_AGENTS_ADMIN'
        """
    )
    op.execute(
        """
        UPDATE unifiedui.tenant_members
        SET role = 'WORKFLOWS_CREATOR'
        WHERE role = 'AUTONOMOUS_AGENTS_CREATOR'
        """
    )

    # ============================================================
    # 8. Update recent_visits resource_type
    # ============================================================
    op.execute(
        """
        UPDATE unifiedui.recent_visits
        SET resource_type = 'workflow'
        WHERE resource_type = 'autonomous_agent'
        """
    )

    # Delete conversation recent visits
    op.execute(
        """
        DELETE FROM unifiedui.recent_visits
        WHERE resource_type = 'conversation'
        """
    )


def downgrade() -> None:
    """Revert workflows tables back to autonomous_agents."""
    # ============================================================
    # 1. Revert recent_visits resource_type
    # ============================================================
    op.execute(
        """
        UPDATE unifiedui.recent_visits
        SET resource_type = 'autonomous_agent'
        WHERE resource_type = 'workflow'
        """
    )

    # ============================================================
    # 2. Revert TenantRoles enum values
    # ============================================================
    op.execute(
        """
        UPDATE unifiedui.tenant_members
        SET role = 'AUTONOMOUS_AGENTS_ADMIN'
        WHERE role = 'WORKFLOWS_ADMIN'
        """
    )
    op.execute(
        """
        UPDATE unifiedui.tenant_members
        SET role = 'AUTONOMOUS_AGENTS_CREATOR'
        WHERE role = 'WORKFLOWS_CREATOR'
        """
    )

    # ============================================================
    # 3. Drop new indexes
    # ============================================================
    op.drop_index("ix_workflows_tenant", table_name="workflows", schema="unifiedui")
    op.drop_index("ix_wm_workflow", table_name="workflow_members", schema="unifiedui")
    op.drop_index("ix_wm_principal", table_name="workflow_members", schema="unifiedui")
    op.drop_index("ix_wt_workflow", table_name="workflow_tags", schema="unifiedui")
    op.drop_index("ix_wt_tag", table_name="workflow_tags", schema="unifiedui")
    op.drop_index("ix_wuf_user", table_name="workflow_user_favorites", schema="unifiedui")
    op.drop_index("ix_wuf_workflow", table_name="workflow_user_favorites", schema="unifiedui")

    # ============================================================
    # 4. Drop new constraints
    # ============================================================
    op.drop_constraint("uq_workflow_tenant_name", "workflows", schema="unifiedui", type_="unique")
    op.drop_constraint("fk_workflow_members_principal", "workflow_members", schema="unifiedui", type_="foreignkey")
    op.drop_constraint("uq_workflow_members", "workflow_members", schema="unifiedui", type_="unique")
    op.drop_constraint(
        "fk_workflow_user_favorites_principal", "workflow_user_favorites", schema="unifiedui", type_="foreignkey"
    )

    # ============================================================
    # 5. Rename columns back
    # ============================================================
    op.alter_column(
        "workflow_members",
        "workflow_id",
        new_column_name="autonomous_agent_id",
        schema="unifiedui",
    )
    op.alter_column(
        "workflow_tags",
        "workflow_id",
        new_column_name="autonomous_agent_id",
        schema="unifiedui",
    )
    op.alter_column(
        "workflow_user_favorites",
        "workflow_id",
        new_column_name="autonomous_agent_id",
        schema="unifiedui",
    )

    # ============================================================
    # 6. Rename tables back
    # ============================================================
    op.rename_table("workflows", "autonomous_agents", schema="unifiedui")
    op.rename_table("workflow_members", "autonomous_agent_members", schema="unifiedui")
    op.rename_table("workflow_tags", "autonomous_agent_tags", schema="unifiedui")
    op.rename_table("workflow_user_favorites", "autonomous_agent_user_favorites", schema="unifiedui")

    # ============================================================
    # 7. Recreate old constraints
    # ============================================================
    op.create_unique_constraint(
        "uq_autonomous_agent_tenant_name", "autonomous_agents", ["tenant_id", "name"], schema="unifiedui"
    )
    op.create_foreign_key(
        "fk_autonomous_agent_members_principal",
        "autonomous_agent_members",
        "principals",
        ["tenant_id", "principal_id"],
        ["tenant_id", "principal_id"],
        source_schema="unifiedui",
        referent_schema="unifiedui",
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_autonomous_agent_members",
        "autonomous_agent_members",
        ["autonomous_agent_id", "principal_id"],
        schema="unifiedui",
    )
    op.create_foreign_key(
        "fk_autonomous_agent_user_favorites_principal",
        "autonomous_agent_user_favorites",
        "principals",
        ["tenant_id", "user_id"],
        ["tenant_id", "principal_id"],
        source_schema="unifiedui",
        referent_schema="unifiedui",
        ondelete="CASCADE",
    )

    # ============================================================
    # 8. Recreate old indexes
    # ============================================================
    op.create_index("ix_autonomous_agents_tenant", "autonomous_agents", ["tenant_id"], schema="unifiedui")
    op.create_index("ix_aam_autonomous_agent", "autonomous_agent_members", ["autonomous_agent_id"], schema="unifiedui")
    op.create_index("ix_aam_principal", "autonomous_agent_members", ["principal_id"], schema="unifiedui")
    op.create_index("ix_aat_autonomous_agent", "autonomous_agent_tags", ["autonomous_agent_id"], schema="unifiedui")
    op.create_index("ix_aat_tag", "autonomous_agent_tags", ["tag_id"], schema="unifiedui")
    op.create_index("ix_aauf_user", "autonomous_agent_user_favorites", ["user_id"], schema="unifiedui")
    op.create_index(
        "ix_aauf_autonomous_agent", "autonomous_agent_user_favorites", ["autonomous_agent_id"], schema="unifiedui"
    )
