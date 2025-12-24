from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    Sequence,
    func,
)
from sqlalchemy.dialects import postgresql, mssql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON
from sqlalchemy import Enum as SAEnum

from aihub.core.database.enums import PermissionActionEnum, TenantRolesEnum, PrincipalTypeEnum


# ---------- Base ----------
class Base(DeclarativeBase):
    pass


# ---------- Portable JSON ----------
# Uses native JSON/JSONB where available; falls back gracefully.
PortableJSON = JSON().with_variant(postgresql.JSONB(), "postgresql").with_variant(mssql.JSON(), "mssql")


# ---------- Enums (DB-agnostic via CHECK constraints) ----------
TenantPermissionSAEnum = SAEnum(
    *TenantRolesEnum.all(),
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
class IdMixin:
    """Mixin for ID field."""
    id: Mapped[str] = mapped_column(String(100), primary_key=True)


class AuditMixin:
    """Mixin for audit fields (timestamps and user tracking)."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(50))
    updated_by: Mapped[Optional[str]] = mapped_column(String(50))


class IdNameDescriptionMixin(IdMixin, AuditMixin):
    """Mixin for entities with ID, name, description and audit fields."""
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(2000))


class TenantScopedMixin:
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)


# ---------- Core ----------
class Tenant(Base, IdNameDescriptionMixin):
    __tablename__ = "tenants"

    members: Mapped[list["TenantMember"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )


class TenantMember(Base, IdMixin, AuditMixin):
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
    roles: Mapped[list["TenantMemberRole"]] = relationship(
        back_populates="tenant_member", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "principal_id", "principal_type", name="uq_tenant_members"),
        Index("ix_tenant_members_tenant", "tenant_id"),
        Index("ix_tenant_members_principal", "principal_id"),
    )


class TenantMemberRole(Base, IdMixin, AuditMixin):
    """
    Roles for tenant members.
    Defines what roles a tenant member has.
    """
    __tablename__ = "tenant_member_roles"

    tenant_member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenant_members.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(TenantPermissionSAEnum, nullable=False)

    tenant_member: Mapped["TenantMember"] = relationship(back_populates="roles")

    __table_args__ = (
        UniqueConstraint("tenant_member_id", "role", name="uq_tenant_member_roles"),
        Index("ix_tmr_tenant_member", "tenant_member_id"),
    )


# ---------- Resources ----------
class CustomGroup(Base, IdNameDescriptionMixin, TenantScopedMixin):
    """Custom group entity."""
    __tablename__ = "custom_groups"

    members: Mapped[list["CustomGroupMember"]] = relationship(
        back_populates="custom_group", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_custom_groups_tenant", "tenant_id"),)


class CustomGroupMember(Base, IdMixin, AuditMixin):
    """Custom group membership table."""
    __tablename__ = "custom_group_members"

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    custom_group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("custom_groups.id", ondelete="CASCADE"), nullable=False
    )
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)
    principal_type: Mapped[str] = mapped_column(PrincipalTypeSAEnum, nullable=False)

    role: Mapped[str] = mapped_column(PermissionActionSAEnum, nullable=False)

    custom_group: Mapped["CustomGroup"] = relationship(back_populates="members")

    __table_args__ = (
        UniqueConstraint("custom_group_id", "principal_id", "principal_type", name="uq_custom_group_members"),
        Index("ix_cgm_custom_group", "custom_group_id"),
        Index("ix_cgm_principal", "principal_id"),
    )


class Application(Base, IdNameDescriptionMixin, TenantScopedMixin):
    __tablename__ = "applications"

    config: Mapped[dict] = mapped_column(PortableJSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    members: Mapped[list["ApplicationMember"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    tags: Mapped[list["ApplicationTag"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    user_favorites: Mapped[list["ApplicationUserFavorite"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_applications_tenant", "tenant_id"),)


class Conversation(Base, IdNameDescriptionMixin, TenantScopedMixin):
    __tablename__ = "conversations"

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    members: Mapped[list["ConversationMember"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    user_favorites: Mapped[list["ConversationUserFavorite"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_conversations_tenant", "tenant_id"),)


class AutonomousAgent(Base, IdNameDescriptionMixin, TenantScopedMixin):
    __tablename__ = "autonomous_agents"

    config: Mapped[dict] = mapped_column(PortableJSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    members: Mapped[list["AutonomousAgentMember"]] = relationship(
        back_populates="autonomous_agent", cascade="all, delete-orphan"
    )
    tags: Mapped[list["AutonomousAgentTag"]] = relationship(
        back_populates="autonomous_agent", cascade="all, delete-orphan"
    )
    user_favorites: Mapped[list["AutonomousAgentUserFavorite"]] = relationship(
        back_populates="autonomous_agent", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_autonomous_agents_tenant", "tenant_id"),)


class Credential(Base, IdNameDescriptionMixin, TenantScopedMixin):
    __tablename__ = "credentials"

    type: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    credential_uri: Mapped[str] = mapped_column(String(2000), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    members: Mapped[list["CredentialMember"]] = relationship(
        back_populates="credential", cascade="all, delete-orphan"
    )
    tags: Mapped[list["CredentialTag"]] = relationship(
        back_populates="credential", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_credentials_tenant", "tenant_id"),)


# ---------- Permission tables ----------
class ApplicationMember(Base, IdMixin, AuditMixin):
    """Application membership table."""
    __tablename__ = "application_members"

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)
    principal_type: Mapped[str] = mapped_column(PrincipalTypeSAEnum, nullable=False)

    role: Mapped[str] = mapped_column(PermissionActionSAEnum, nullable=False)

    application: Mapped["Application"] = relationship(back_populates="members")

    __table_args__ = (
        UniqueConstraint("application_id", "principal_id", "principal_type", name="uq_application_members"),
        Index("ix_am_application", "application_id"),
        Index("ix_am_principal", "principal_id"),
    )


class ConversationMember(Base, IdMixin, AuditMixin):
    """Conversation membership table."""
    __tablename__ = "conversation_members"

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)
    principal_type: Mapped[str] = mapped_column(PrincipalTypeSAEnum, nullable=False)

    role: Mapped[str] = mapped_column(PermissionActionSAEnum, nullable=False)

    conversation: Mapped["Conversation"] = relationship(back_populates="members")

    __table_args__ = (
        UniqueConstraint("conversation_id", "principal_id", "principal_type", name="uq_conversation_members"),
        Index("ix_cm_conversation", "conversation_id"),
        Index("ix_cm_principal", "principal_id"),
    )


class AutonomousAgentMember(Base, IdMixin, AuditMixin):
    """Autonomous agent membership table."""
    __tablename__ = "autonomous_agent_members"

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    autonomous_agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("autonomous_agents.id", ondelete="CASCADE"), nullable=False
    )
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)
    principal_type: Mapped[str] = mapped_column(PrincipalTypeSAEnum, nullable=False)

    role: Mapped[str] = mapped_column(PermissionActionSAEnum, nullable=False)

    autonomous_agent: Mapped["AutonomousAgent"] = relationship(back_populates="members")

    __table_args__ = (
        UniqueConstraint("autonomous_agent_id", "principal_id", "principal_type", name="uq_autonomous_agent_members"),
        Index("ix_aam_autonomous_agent", "autonomous_agent_id"),
        Index("ix_aam_principal", "principal_id"),
    )


class CredentialMember(Base, IdMixin, AuditMixin):
    """Credential membership table."""
    __tablename__ = "credential_members"

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    credential_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("credentials.id", ondelete="CASCADE"), nullable=False
    )
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)
    principal_type: Mapped[str] = mapped_column(PrincipalTypeSAEnum, nullable=False)

    role: Mapped[str] = mapped_column(PermissionActionSAEnum, nullable=False)

    credential: Mapped["Credential"] = relationship(back_populates="members")

    __table_args__ = (
        UniqueConstraint("credential_id", "principal_id", "principal_type", name="uq_credential_members"),
        Index("ix_crm_credential", "credential_id"),
        Index("ix_crm_principal", "principal_id"),
    )


# ---------- Development Platforms ----------
class DevelopmentPlatform(Base, IdNameDescriptionMixin, TenantScopedMixin):
    """Development platform entity for embedding external development tools."""
    __tablename__ = "development_platforms"

    type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    iframe_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    config: Mapped[dict] = mapped_column(PortableJSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    members: Mapped[list["DevelopmentPlatformMember"]] = relationship(
        back_populates="development_platform", cascade="all, delete-orphan"
    )
    tags: Mapped[list["DevelopmentPlatformTag"]] = relationship(
        back_populates="development_platform", cascade="all, delete-orphan"
    )
    user_favorites: Mapped[list["DevelopmentPlatformUserFavorite"]] = relationship(
        back_populates="development_platform", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_development_platforms_tenant", "tenant_id"),)


class DevelopmentPlatformMember(Base, IdMixin, AuditMixin):
    """Development platform membership table."""
    __tablename__ = "development_platform_members"

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    development_platform_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("development_platforms.id", ondelete="CASCADE"), nullable=False
    )
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)
    principal_type: Mapped[str] = mapped_column(PrincipalTypeSAEnum, nullable=False)

    role: Mapped[str] = mapped_column(PermissionActionSAEnum, nullable=False)

    development_platform: Mapped["DevelopmentPlatform"] = relationship(back_populates="members")

    __table_args__ = (
        UniqueConstraint("development_platform_id", "principal_id", "principal_type", name="uq_development_platform_members"),
        Index("ix_dpm_development_platform", "development_platform_id"),
        Index("ix_dpm_principal", "principal_id"),
    )


# ---------- Chat Widgets ----------
class ChatWidget(Base, IdNameDescriptionMixin, TenantScopedMixin):
    """Chat widget entity for embedding chat interfaces."""
    __tablename__ = "chat_widgets"

    type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    config: Mapped[dict] = mapped_column(PortableJSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    members: Mapped[list["ChatWidgetMember"]] = relationship(
        back_populates="chat_widget", cascade="all, delete-orphan"
    )
    tags: Mapped[list["ChatWidgetTag"]] = relationship(
        back_populates="chat_widget", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_chat_widgets_tenant", "tenant_id"),)


class ChatWidgetMember(Base, IdMixin, AuditMixin):
    """Chat widget membership table."""
    __tablename__ = "chat_widget_members"

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    chat_widget_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_widgets.id", ondelete="CASCADE"), nullable=False
    )
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)
    principal_type: Mapped[str] = mapped_column(PrincipalTypeSAEnum, nullable=False)

    role: Mapped[str] = mapped_column(PermissionActionSAEnum, nullable=False)

    chat_widget: Mapped["ChatWidget"] = relationship(back_populates="members")

    __table_args__ = (
        UniqueConstraint("chat_widget_id", "principal_id", "principal_type", name="uq_chat_widget_members"),
        Index("ix_cwm_chat_widget", "chat_widget_id"),
        Index("ix_cwm_principal", "principal_id"),
    )


# ---------- Tags ----------
# Sequence for auto-incrementing tag IDs starting at 10000 (PostgreSQL only)
# SQLite will use AUTOINCREMENT instead
tag_id_seq = Sequence('tag_id_seq', start=10000, optional=True)


class Tag(Base, AuditMixin):
    """Tag entity for categorizing resources."""
    __tablename__ = "tags"

    # Note: For PostgreSQL, the sequence starts at 10000
    # For SQLite (tests), it starts at 1 (standard autoincrement)
    id: Mapped[int] = mapped_column(
        Integer, tag_id_seq, primary_key=True, autoincrement=True
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships to junction tables
    application_tags: Mapped[list["ApplicationTag"]] = relationship(
        back_populates="tag", cascade="all, delete-orphan"
    )
    autonomous_agent_tags: Mapped[list["AutonomousAgentTag"]] = relationship(
        back_populates="tag", cascade="all, delete-orphan"
    )
    chat_widget_tags: Mapped[list["ChatWidgetTag"]] = relationship(
        back_populates="tag", cascade="all, delete-orphan"
    )
    credential_tags: Mapped[list["CredentialTag"]] = relationship(
        back_populates="tag", cascade="all, delete-orphan"
    )
    development_platform_tags: Mapped[list["DevelopmentPlatformTag"]] = relationship(
        back_populates="tag", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_tag_tenant_name"),
        Index("ix_tags_tenant", "tenant_id"),
        Index("ix_tags_name", "name"),
    )


class ApplicationTag(Base):
    """Junction table for application tags."""
    __tablename__ = "application_tags"

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, primary_key=True)
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    application_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )

    tag: Mapped["Tag"] = relationship(back_populates="application_tags")
    application: Mapped["Application"] = relationship(back_populates="tags")

    __table_args__ = (
        Index("ix_at_application", "application_id"),
        Index("ix_at_tag", "tag_id"),
    )


class AutonomousAgentTag(Base):
    """Junction table for autonomous agent tags."""
    __tablename__ = "autonomous_agent_tags"

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, primary_key=True)
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    autonomous_agent_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("autonomous_agents.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )

    tag: Mapped["Tag"] = relationship(back_populates="autonomous_agent_tags")
    autonomous_agent: Mapped["AutonomousAgent"] = relationship(back_populates="tags")

    __table_args__ = (
        Index("ix_aat_autonomous_agent", "autonomous_agent_id"),
        Index("ix_aat_tag", "tag_id"),
    )


class ChatWidgetTag(Base):
    """Junction table for chat widget tags."""
    __tablename__ = "chat_widget_tags"

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, primary_key=True)
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    chat_widget_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("chat_widgets.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )

    tag: Mapped["Tag"] = relationship(back_populates="chat_widget_tags")
    chat_widget: Mapped["ChatWidget"] = relationship(back_populates="tags")

    __table_args__ = (
        Index("ix_cwt_chat_widget", "chat_widget_id"),
        Index("ix_cwt_tag", "tag_id"),
    )


class CredentialTag(Base):
    """Junction table for credential tags."""
    __tablename__ = "credential_tags"

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, primary_key=True)
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    credential_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("credentials.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )

    tag: Mapped["Tag"] = relationship(back_populates="credential_tags")
    credential: Mapped["Credential"] = relationship(back_populates="tags")

    __table_args__ = (
        Index("ix_crt_credential", "credential_id"),
        Index("ix_crt_tag", "tag_id"),
    )


class DevelopmentPlatformTag(Base):
    """Junction table for development platform tags."""
    __tablename__ = "development_platform_tags"

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, primary_key=True)
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    development_platform_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("development_platforms.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )

    tag: Mapped["Tag"] = relationship(back_populates="development_platform_tags")
    development_platform: Mapped["DevelopmentPlatform"] = relationship(back_populates="tags")

    __table_args__ = (
        Index("ix_dpt_development_platform", "development_platform_id"),
        Index("ix_dpt_tag", "tag_id"),
    )


# ---------- User Favorites ----------
class ApplicationUserFavorite(Base, AuditMixin):
    """User favorites for applications."""
    __tablename__ = "application_user_favorites"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    user_id: Mapped[str] = mapped_column(String(50), nullable=False, primary_key=True)
    application_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )

    application: Mapped["Application"] = relationship(back_populates="user_favorites")

    __table_args__ = (
        Index("ix_auf_user", "user_id"),
        Index("ix_auf_application", "application_id"),
    )


class AutonomousAgentUserFavorite(Base, AuditMixin):
    """User favorites for autonomous agents."""
    __tablename__ = "autonomous_agent_user_favorites"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    user_id: Mapped[str] = mapped_column(String(50), nullable=False, primary_key=True)
    autonomous_agent_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("autonomous_agents.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )

    autonomous_agent: Mapped["AutonomousAgent"] = relationship(back_populates="user_favorites")

    __table_args__ = (
        Index("ix_aauf_user", "user_id"),
        Index("ix_aauf_autonomous_agent", "autonomous_agent_id"),
    )


class DevelopmentPlatformUserFavorite(Base, AuditMixin):
    """User favorites for development platforms."""
    __tablename__ = "development_platform_user_favorites"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    user_id: Mapped[str] = mapped_column(String(50), nullable=False, primary_key=True)
    development_platform_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("development_platforms.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )

    development_platform: Mapped["DevelopmentPlatform"] = relationship(back_populates="user_favorites")

    __table_args__ = (
        Index("ix_dpuf_user", "user_id"),
        Index("ix_dpuf_development_platform", "development_platform_id"),
    )


class ConversationUserFavorite(Base, AuditMixin):
    """User favorites for conversations."""
    __tablename__ = "conversation_user_favorites"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    user_id: Mapped[str] = mapped_column(String(50), nullable=False, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="user_favorites")

    __table_args__ = (
        Index("ix_cuf_user", "user_id"),
        Index("ix_cuf_conversation", "conversation_id"),
    )

