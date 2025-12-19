from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects import postgresql, mssql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON
from sqlalchemy import Enum as SAEnum

from aihub.core.database.enums import PermissionActionEnum, TenantPermissionEnum, PrincipalTypeEnum


# ---------- Base ----------
class Base(DeclarativeBase):
    pass


# ---------- Portable JSON ----------
# Uses native JSON/JSONB where available; falls back gracefully.
PortableJSON = JSON().with_variant(postgresql.JSONB(), "postgresql").with_variant(mssql.JSON(), "mssql")


# ---------- Enums (DB-agnostic via CHECK constraints) ----------
TenantPermissionSAEnum = SAEnum(
    *TenantPermissionEnum.all(),
    name="tenant_role",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)

PermissionActionSAEnum = SAEnum(
    *PermissionActionEnum.all(),
    name="permission_action",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)

PrincipalTypeSAEnum = SAEnum(
    *PrincipalTypeEnum.all(),
    name="principal_type",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)


# ---------- Mixins ----------
class IdNameDescriptionMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(50))
    updated_by: Mapped[Optional[str]] = mapped_column(String(50))


class TenantScopedMixin:
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)


# ---------- Core ----------
class Tenant(Base, IdNameDescriptionMixin):
    __tablename__ = "tenants"

    members: Mapped[list["TenantMember"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )


class TenantMember(Base, IdNameDescriptionMixin):
    """
    Tenant membership table.
    Tracks which principals (users, identity groups, custom groups) are members of a tenant.
    """
    __tablename__ = "tenant_members"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)
    principal_type: Mapped[str] = mapped_column(PrincipalTypeSAEnum, nullable=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="members")
    permissions: Mapped[list["TenantMemberPermission"]] = relationship(
        back_populates="tenant_member", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "principal_id", "principal_type", name="uq_tenant_members"),
        Index("ix_tenant_members_tenant", "tenant_id"),
        Index("ix_tenant_members_principal", "principal_id"),
    )


class TenantMemberPermission(Base, IdNameDescriptionMixin):
    """
    Permissions/roles for tenant members.
    Defines what roles/permissions a tenant member has.
    """
    __tablename__ = "tenant_member_permissions"

    tenant_member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenant_members.id", ondelete="CASCADE"), nullable=False
    )
    permission: Mapped[str] = mapped_column(TenantPermissionSAEnum, nullable=False)

    tenant_member: Mapped["TenantMember"] = relationship(back_populates="permissions")

    __table_args__ = (
        UniqueConstraint("tenant_member_id", "permission", name="uq_tenant_member_permissions"),
        Index("ix_tmp_tenant_member", "tenant_member_id"),
    )


# ---------- Resources ----------
class CustomGroup(Base, IdNameDescriptionMixin, TenantScopedMixin):
    """Custom group entity."""
    __tablename__ = "custom_groups"

    members: Mapped[list["CustomGroupMember"]] = relationship(
        back_populates="custom_group", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_custom_groups_tenant", "tenant_id"),)


class CustomGroupMember(Base, IdNameDescriptionMixin):
    """Custom group membership table."""
    __tablename__ = "custom_group_members"

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    custom_group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("custom_groups.id", ondelete="CASCADE"), nullable=False
    )
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)
    principal_type: Mapped[str] = mapped_column(PrincipalTypeSAEnum, nullable=False)

    custom_group: Mapped["CustomGroup"] = relationship(back_populates="members")
    permissions: Mapped[list["CustomGroupMemberPermission"]] = relationship(
        back_populates="custom_group_member", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("custom_group_id", "principal_id", "principal_type", name="uq_custom_group_members"),
        Index("ix_cgm_custom_group", "custom_group_id"),
        Index("ix_cgm_principal", "principal_id"),
    )


class CustomGroupMemberPermission(Base, IdNameDescriptionMixin):
    """Permissions for custom group members."""
    __tablename__ = "custom_group_member_permissions"

    custom_group_member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("custom_group_members.id", ondelete="CASCADE"), nullable=False
    )
    permission: Mapped[str] = mapped_column(PermissionActionSAEnum, nullable=False)

    custom_group_member: Mapped["CustomGroupMember"] = relationship(back_populates="permissions")

    __table_args__ = (
        UniqueConstraint("custom_group_member_id", "permission", name="uq_custom_group_member_permissions"),
        Index("ix_cgmp_member", "custom_group_member_id"),
    )


class Application(Base, IdNameDescriptionMixin, TenantScopedMixin):
    __tablename__ = "applications"

    config: Mapped[dict] = mapped_column(PortableJSON, nullable=False, default=dict)

    members: Mapped[list["ApplicationMember"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_applications_tenant", "tenant_id"),)


class Conversation(Base, IdNameDescriptionMixin, TenantScopedMixin):
    __tablename__ = "conversations"

    members: Mapped[list["ConversationMember"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_conversations_tenant", "tenant_id"),)


class AutonomousAgent(Base, IdNameDescriptionMixin, TenantScopedMixin):
    __tablename__ = "autonomous_agents"

    config: Mapped[dict] = mapped_column(PortableJSON, nullable=False, default=dict)

    members: Mapped[list["AutonomousAgentMember"]] = relationship(
        back_populates="autonomous_agent", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_autonomous_agents_tenant", "tenant_id"),)


class Credential(Base, IdNameDescriptionMixin, TenantScopedMixin):
    __tablename__ = "credentials"

    type: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    credential_uri: Mapped[str] = mapped_column(String(2000), nullable=False)

    members: Mapped[list["CredentialMember"]] = relationship(
        back_populates="credential", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_credentials_tenant", "tenant_id"),)


# ---------- Permission tables ----------
class ApplicationMember(Base, IdNameDescriptionMixin):
    """Application membership table."""
    __tablename__ = "application_members"

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)
    principal_type: Mapped[str] = mapped_column(PrincipalTypeSAEnum, nullable=False)

    application: Mapped["Application"] = relationship(back_populates="members")
    permissions: Mapped[list["ApplicationMemberPermission"]] = relationship(
        back_populates="application_member", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("application_id", "principal_id", "principal_type", name="uq_application_members"),
        Index("ix_am_application", "application_id"),
        Index("ix_am_principal", "principal_id"),
    )


class ApplicationMemberPermission(Base, IdNameDescriptionMixin):
    """Permissions for application members."""
    __tablename__ = "application_member_permissions"

    application_member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("application_members.id", ondelete="CASCADE"), nullable=False
    )
    permission: Mapped[str] = mapped_column(PermissionActionSAEnum, nullable=False)

    application_member: Mapped["ApplicationMember"] = relationship(back_populates="permissions")

    __table_args__ = (
        UniqueConstraint("application_member_id", "permission", name="uq_application_member_permissions"),
        Index("ix_amp_member", "application_member_id"),
    )


class ConversationMember(Base, IdNameDescriptionMixin):
    """Conversation membership table."""
    __tablename__ = "conversation_members"

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)
    principal_type: Mapped[str] = mapped_column(PrincipalTypeSAEnum, nullable=False)

    conversation: Mapped["Conversation"] = relationship(back_populates="members")
    permissions: Mapped[list["ConversationMemberPermission"]] = relationship(
        back_populates="conversation_member", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("conversation_id", "principal_id", "principal_type", name="uq_conversation_members"),
        Index("ix_cm_conversation", "conversation_id"),
        Index("ix_cm_principal", "principal_id"),
    )


class ConversationMemberPermission(Base, IdNameDescriptionMixin):
    """Permissions for conversation members."""
    __tablename__ = "conversation_member_permissions"

    conversation_member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversation_members.id", ondelete="CASCADE"), nullable=False
    )
    permission: Mapped[str] = mapped_column(PermissionActionSAEnum, nullable=False)

    conversation_member: Mapped["ConversationMember"] = relationship(back_populates="permissions")

    __table_args__ = (
        UniqueConstraint("conversation_member_id", "permission", name="uq_conversation_member_permissions"),
        Index("ix_cmp_member", "conversation_member_id"),
    )


class AutonomousAgentMember(Base, IdNameDescriptionMixin):
    """Autonomous agent membership table."""
    __tablename__ = "autonomous_agent_members"

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    autonomous_agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("autonomous_agents.id", ondelete="CASCADE"), nullable=False
    )
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)
    principal_type: Mapped[str] = mapped_column(PrincipalTypeSAEnum, nullable=False)

    autonomous_agent: Mapped["AutonomousAgent"] = relationship(back_populates="members")
    permissions: Mapped[list["AutonomousAgentMemberPermission"]] = relationship(
        back_populates="autonomous_agent_member", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("autonomous_agent_id", "principal_id", "principal_type", name="uq_autonomous_agent_members"),
        Index("ix_aam_autonomous_agent", "autonomous_agent_id"),
        Index("ix_aam_principal", "principal_id"),
    )


class AutonomousAgentMemberPermission(Base, IdNameDescriptionMixin):
    """Permissions for autonomous agent members."""
    __tablename__ = "autonomous_agent_member_permissions"

    autonomous_agent_member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("autonomous_agent_members.id", ondelete="CASCADE"), nullable=False
    )
    permission: Mapped[str] = mapped_column(PermissionActionSAEnum, nullable=False)

    autonomous_agent_member: Mapped["AutonomousAgentMember"] = relationship(back_populates="permissions")

    __table_args__ = (
        UniqueConstraint("autonomous_agent_member_id", "permission", name="uq_autonomous_agent_member_permissions"),
        Index("ix_aamp_member", "autonomous_agent_member_id"),
    )


class CredentialMember(Base, IdNameDescriptionMixin):
    """Credential membership table."""
    __tablename__ = "credential_members"

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    credential_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("credentials.id", ondelete="CASCADE"), nullable=False
    )
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)
    principal_type: Mapped[str] = mapped_column(PrincipalTypeSAEnum, nullable=False)

    credential: Mapped["Credential"] = relationship(back_populates="members")
    permissions: Mapped[list["CredentialMemberPermission"]] = relationship(
        back_populates="credential_member", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("credential_id", "principal_id", "principal_type", name="uq_credential_members"),
        Index("ix_crm_credential", "credential_id"),
        Index("ix_crm_principal", "principal_id"),
    )


class CredentialMemberPermission(Base, IdNameDescriptionMixin):
    """Permissions for credential members."""
    __tablename__ = "credential_member_permissions"

    credential_member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("credential_members.id", ondelete="CASCADE"), nullable=False
    )
    permission: Mapped[str] = mapped_column(PermissionActionSAEnum, nullable=False)

    credential_member: Mapped["CredentialMember"] = relationship(back_populates="permissions")

    __table_args__ = (
        UniqueConstraint("credential_member_id", "permission", name="uq_credential_member_permissions"),
        Index("ix_crmp_member", "credential_member_id"),
    )
