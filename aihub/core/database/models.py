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


# ---------- Base ----------
class Base(DeclarativeBase):
    pass


# ---------- Portable JSON ----------
# Uses native JSON/JSONB where available; falls back gracefully.
PortableJSON = JSON().with_variant(postgresql.JSONB(), "postgresql").with_variant(mssql.JSON(), "mssql")


# ---------- Enums (DB-agnostic via CHECK constraints) ----------
TenantRoleEnum = SAEnum(
    "READER",
    "GLOBAL_ADMIN",
    "CUSTOM_GROUPS_ADMIN",
    "APPLICATIONS_ADMIN",
    "CREDENTIALS_ADMIN",
    "AUTONOMOUS_AGENTS_ADMIN",
    name="tenant_role",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)

PermissionActionEnum = SAEnum(
    "READ",
    "WRITE",
    "ADMIN",
    name="permission_action",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)

PrincipalTypeEnum = SAEnum(
    "IDENTITY_USER",
    "IDENTITY_GROUP",
    "CUSTOM_GROUP",
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

    principals: Mapped[list["TenantPrincipal"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )


class TenantPrincipal(Base, IdNameDescriptionMixin):
    """
    Special permissions table for tenants: tenant_principals
    principal_id is a free-form string (max 50).
    principal_type indicates whether it's a user, identity group, or custom group.
    """
    __tablename__ = "tenant_principals"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)
    principal_type: Mapped[str] = mapped_column(PrincipalTypeEnum, nullable=False)
    role: Mapped[str] = mapped_column(TenantRoleEnum, nullable=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="principals")

    __table_args__ = (
        UniqueConstraint("tenant_id", "principal_id", "principal_type", "role", name="uq_tenant_principals"),
        Index("ix_tenant_principals_tenant", "tenant_id"),
        Index("ix_tenant_principals_principal", "principal_id"),
    )


# ---------- Resources ----------
class CustomGroup(Base, IdNameDescriptionMixin, TenantScopedMixin):
    __tablename__ = "custom_groups"

    permissions: Mapped[list["CustomGroupPermission"]] = relationship(
        back_populates="custom_group", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_custom_groups_tenant", "tenant_id"),)


class Application(Base, IdNameDescriptionMixin, TenantScopedMixin):
    __tablename__ = "applications"

    config: Mapped[dict] = mapped_column(PortableJSON, nullable=False, default=dict)

    permissions: Mapped[list["ApplicationPermission"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_applications_tenant", "tenant_id"),)


class Conversation(Base, IdNameDescriptionMixin, TenantScopedMixin):
    __tablename__ = "conversations"

    permissions: Mapped[list["ConversationPermission"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_conversations_tenant", "tenant_id"),)


class AutonomousAgent(Base, IdNameDescriptionMixin, TenantScopedMixin):
    __tablename__ = "autonomous_agents"

    config: Mapped[dict] = mapped_column(PortableJSON, nullable=False, default=dict)

    permissions: Mapped[list["AutonomousAgentPermission"]] = relationship(
        back_populates="autonomous_agent", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_autonomous_agents_tenant", "tenant_id"),)


class Credential(Base, IdNameDescriptionMixin, TenantScopedMixin):
    __tablename__ = "credentials"

    config: Mapped[dict] = mapped_column(PortableJSON, nullable=False, default=dict)

    permissions: Mapped[list["CredentialPermission"]] = relationship(
        back_populates="credential", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_credentials_tenant", "tenant_id"),)


# ---------- Permission tables ----------
class CustomGroupPermission(Base, IdNameDescriptionMixin, TenantScopedMixin):
    __tablename__ = "custom_group_permissions"

    custom_group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("custom_groups.id", ondelete="CASCADE"), nullable=False
    )
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(PermissionActionEnum, nullable=False)

    custom_group: Mapped["CustomGroup"] = relationship(back_populates="permissions")

    __table_args__ = (
        UniqueConstraint("tenant_id", "custom_group_id", "principal_id", "action", name="uq_cgp"),
        Index("ix_cgp_lookup", "tenant_id", "custom_group_id"),
        Index("ix_cgp_principal", "principal_id"),
    )


class ApplicationPermission(Base, IdNameDescriptionMixin, TenantScopedMixin):
    __tablename__ = "application_permissions"

    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(PermissionActionEnum, nullable=False)

    application: Mapped["Application"] = relationship(back_populates="permissions")

    __table_args__ = (
        UniqueConstraint("tenant_id", "application_id", "principal_id", "action", name="uq_ap"),
        Index("ix_ap_lookup", "tenant_id", "application_id"),
        Index("ix_ap_principal", "principal_id"),
    )


class ConversationPermission(Base, IdNameDescriptionMixin, TenantScopedMixin):
    __tablename__ = "conversation_permissions"

    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(PermissionActionEnum, nullable=False)

    conversation: Mapped["Conversation"] = relationship(back_populates="permissions")

    __table_args__ = (
        UniqueConstraint("tenant_id", "conversation_id", "principal_id", "action", name="uq_cp"),
        Index("ix_cp_lookup", "tenant_id", "conversation_id"),
        Index("ix_cp_principal", "principal_id"),
    )


class AutonomousAgentPermission(Base, IdNameDescriptionMixin, TenantScopedMixin):
    __tablename__ = "autonomous_agent_permissions"

    autonomous_agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("autonomous_agents.id", ondelete="CASCADE"), nullable=False
    )
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(PermissionActionEnum, nullable=False)

    autonomous_agent: Mapped["AutonomousAgent"] = relationship(back_populates="permissions")

    __table_args__ = (
        UniqueConstraint("tenant_id", "autonomous_agent_id", "principal_id", "action", name="uq_aap"),
        Index("ix_aap_lookup", "tenant_id", "autonomous_agent_id"),
        Index("ix_aap_principal", "principal_id"),
    )


class CredentialPermission(Base, IdNameDescriptionMixin, TenantScopedMixin):
    __tablename__ = "credential_permissions"

    credential_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("credentials.id", ondelete="CASCADE"), nullable=False
    )
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(PermissionActionEnum, nullable=False)

    credential: Mapped["Credential"] = relationship(back_populates="permissions")

    __table_args__ = (
        UniqueConstraint("tenant_id", "credential_id", "principal_id", "action", name="uq_crp"),
        Index("ix_crp_lookup", "tenant_id", "credential_id"),
        Index("ix_crp_principal", "principal_id"),
    )
