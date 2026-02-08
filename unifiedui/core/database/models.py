from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    Integer,
    String,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    UniqueConstraint,
    Sequence,
    func,
)
from sqlalchemy.dialects import postgresql, mssql
from sqlalchemy.dialects.postgresql import TIMESTAMP as PG_TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, validates
from sqlalchemy.types import JSON, TypeDecorator
from sqlalchemy import Enum as SAEnum

from unifiedui.core.database.enums import PermissionActionEnum, TenantRolesEnum, PrincipalTypeEnum, ApplicationTypeEnum, AutonomousAgentTypeEnum, AIModelTypeEnum, AIModelProviderEnum


# ---------- Utility functions ----------
def utc_now() -> datetime:
    """Return current UTC time with microsecond precision."""
    return datetime.now(timezone.utc)


# ---------- Custom DateTime with microsecond precision ----------
class HighPrecisionDateTime(TypeDecorator):
    """DateTime type that ensures microsecond precision across databases."""
    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            # PostgreSQL TIMESTAMP with 6 decimal places (microseconds)
            return dialect.type_descriptor(PG_TIMESTAMP(precision=6, timezone=True))
        return dialect.type_descriptor(DateTime(timezone=True))


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

ApplicationTypeSAEnum = SAEnum(
    *ApplicationTypeEnum.all(),
    name="application_type",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)

AutonomousAgentTypeSAEnum = SAEnum(
    *AutonomousAgentTypeEnum.all(),
    name="autonomous_agent_type",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)

AIModelTypeSAEnum = SAEnum(
    *AIModelTypeEnum.all(),
    name="ai_model_type",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)

AIModelProviderSAEnum = SAEnum(
    *AIModelProviderEnum.all(),
    name="ai_model_provider",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)


# ---------- Mixins ----------
class IdMixin:
    """Mixin for ID field."""
    id: Mapped[str] = mapped_column(String(36), primary_key=True)


class AuditMixin:
    """Mixin for audit fields (timestamps and user tracking)."""
    created_at: Mapped[datetime] = mapped_column(
        HighPrecisionDateTime(), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        HighPrecisionDateTime(), nullable=False, default=utc_now, onupdate=utc_now
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
    principals: Mapped[list["Principal"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )


class TenantMember(Base, IdMixin, AuditMixin):
    """
    Tenant membership and roles.
    Links directly to Principals via (tenant_id, principal_id).
    """
    __tablename__ = "tenant_members"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)
    role: Mapped[str] = mapped_column(TenantPermissionSAEnum, nullable=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="members")
    principal: Mapped["Principal"] = relationship(
        foreign_keys="[TenantMember.tenant_id, TenantMember.principal_id]",
        primaryjoin="and_(TenantMember.tenant_id == Principal.tenant_id, TenantMember.principal_id == Principal.principal_id)",
        overlaps="members,tenant"
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "principal_id"],
            ["principals.tenant_id", "principals.principal_id"],
            ondelete="CASCADE",
            name="fk_tenant_members_principal"
        ),
        UniqueConstraint("tenant_id", "principal_id", "role", name="uq_tenant_members"),
        Index("ix_tm_tenant", "tenant_id"),
        Index("ix_tm_principal", "principal_id"),
    )


# ---------- Principals ----------
class Principal(Base):
    """
    Principal entity representing users, identity groups, and custom groups.
    All principals (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP) are stored here.
    """
    __tablename__ = "principals"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False, primary_key=True)
    principal_type: Mapped[str] = mapped_column(PrincipalTypeSAEnum, nullable=False)
    mail: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    principal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        HighPrecisionDateTime(), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        HighPrecisionDateTime(), nullable=False, default=utc_now, onupdate=utc_now
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="principals")
    custom_group_members: Mapped[list["CustomGroupMember"]] = relationship(
        back_populates="custom_group",
        foreign_keys="[CustomGroupMember.tenant_id, CustomGroupMember.custom_group_id]",
        primaryjoin="and_(Principal.tenant_id == CustomGroupMember.tenant_id, Principal.principal_id == CustomGroupMember.custom_group_id)",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_principals_tenant", "tenant_id"),
        Index("ix_principals_principal_type", "principal_type"),
        Index("ix_principals_mail", "mail"),
        Index("ix_principals_display_name", "display_name"),
    )


class CustomGroupMember(Base, IdMixin, AuditMixin):
    """
    Custom group membership table.
    Tracks which principals (users, identity groups) are members of custom groups.
    Custom groups themselves are stored in the principals table with type CUSTOM_GROUP.
    """
    __tablename__ = "custom_group_members"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    custom_group_id: Mapped[str] = mapped_column(String(50), nullable=False)
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)
    role: Mapped[str] = mapped_column(PermissionActionSAEnum, nullable=False)

    # Relationships
    custom_group: Mapped["Principal"] = relationship(
        back_populates="custom_group_members",
        foreign_keys="[CustomGroupMember.tenant_id, CustomGroupMember.custom_group_id]",
        primaryjoin="and_(CustomGroupMember.tenant_id == Principal.tenant_id, CustomGroupMember.custom_group_id == Principal.principal_id)"
    )
    member_principal: Mapped["Principal"] = relationship(
        foreign_keys="[CustomGroupMember.tenant_id, CustomGroupMember.principal_id]",
        primaryjoin="and_(CustomGroupMember.tenant_id == Principal.tenant_id, CustomGroupMember.principal_id == Principal.principal_id)",
        overlaps="custom_group,custom_group_members"
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "custom_group_id"],
            ["principals.tenant_id", "principals.principal_id"],
            ondelete="CASCADE",
            name="fk_custom_group_members_custom_group"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "principal_id"],
            ["principals.tenant_id", "principals.principal_id"],
            ondelete="CASCADE",
            name="fk_custom_group_members_principal"
        ),
        UniqueConstraint("tenant_id", "custom_group_id", "principal_id", name="uq_custom_group_members"),
        Index("ix_cgm_tenant", "tenant_id"),
        Index("ix_cgm_custom_group", "custom_group_id"),
        Index("ix_cgm_principal", "principal_id"),
    )


class Application(Base, IdNameDescriptionMixin, TenantScopedMixin):
    __tablename__ = "applications"

    type: Mapped[str] = mapped_column(ApplicationTypeSAEnum, nullable=False)
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

    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    ext_conversation_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, default=None
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    application: Mapped["Application"] = relationship()
    members: Mapped[list["ConversationMember"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    user_favorites: Mapped[list["ConversationUserFavorite"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_conversations_tenant", "tenant_id"),
        Index("ix_conversations_application", "application_id"),
    )


class AutonomousAgent(Base, IdNameDescriptionMixin, TenantScopedMixin):
    __tablename__ = "autonomous_agents"

    type: Mapped[str] = mapped_column(AutonomousAgentTypeSAEnum, nullable=False)
    config: Mapped[dict] = mapped_column(PortableJSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_api_keys: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    primary_key_vault_uri: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    secondary_key_vault_uri: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    last_full_import: Mapped[Optional[datetime]] = mapped_column(
        HighPrecisionDateTime(), nullable=True, default=None
    )

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

    role: Mapped[str] = mapped_column(PermissionActionSAEnum, nullable=False)

    application: Mapped["Application"] = relationship(back_populates="members")
    principal: Mapped["Principal"] = relationship(
        foreign_keys="[ApplicationMember.tenant_id, ApplicationMember.principal_id]",
        primaryjoin="and_(ApplicationMember.tenant_id == Principal.tenant_id, ApplicationMember.principal_id == Principal.principal_id)"
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "principal_id"],
            ["principals.tenant_id", "principals.principal_id"],
            ondelete="CASCADE",
            name="fk_application_members_principal"
        ),
        UniqueConstraint("application_id", "principal_id", name="uq_application_members"),
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

    role: Mapped[str] = mapped_column(PermissionActionSAEnum, nullable=False)

    conversation: Mapped["Conversation"] = relationship(back_populates="members")
    principal: Mapped["Principal"] = relationship(
        foreign_keys="[ConversationMember.tenant_id, ConversationMember.principal_id]",
        primaryjoin="and_(ConversationMember.tenant_id == Principal.tenant_id, ConversationMember.principal_id == Principal.principal_id)"
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "principal_id"],
            ["principals.tenant_id", "principals.principal_id"],
            ondelete="CASCADE",
            name="fk_conversation_members_principal"
        ),
        UniqueConstraint("conversation_id", "principal_id", name="uq_conversation_members"),
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

    role: Mapped[str] = mapped_column(PermissionActionSAEnum, nullable=False)

    autonomous_agent: Mapped["AutonomousAgent"] = relationship(back_populates="members")
    principal: Mapped["Principal"] = relationship(
        foreign_keys="[AutonomousAgentMember.tenant_id, AutonomousAgentMember.principal_id]",
        primaryjoin="and_(AutonomousAgentMember.tenant_id == Principal.tenant_id, AutonomousAgentMember.principal_id == Principal.principal_id)"
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "principal_id"],
            ["principals.tenant_id", "principals.principal_id"],
            ondelete="CASCADE",
            name="fk_autonomous_agent_members_principal"
        ),
        UniqueConstraint("autonomous_agent_id", "principal_id", name="uq_autonomous_agent_members"),
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

    role: Mapped[str] = mapped_column(PermissionActionSAEnum, nullable=False)

    credential: Mapped["Credential"] = relationship(back_populates="members")
    principal: Mapped["Principal"] = relationship(
        foreign_keys="[CredentialMember.tenant_id, CredentialMember.principal_id]",
        primaryjoin="and_(CredentialMember.tenant_id == Principal.tenant_id, CredentialMember.principal_id == Principal.principal_id)"
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "principal_id"],
            ["principals.tenant_id", "principals.principal_id"],
            ondelete="CASCADE",
            name="fk_credential_members_principal"
        ),
        UniqueConstraint("credential_id", "principal_id", name="uq_credential_members"),
        Index("ix_crm_credential", "credential_id"),
        Index("ix_crm_principal", "principal_id"),
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

    role: Mapped[str] = mapped_column(PermissionActionSAEnum, nullable=False)

    chat_widget: Mapped["ChatWidget"] = relationship(back_populates="members")
    principal: Mapped["Principal"] = relationship(
        foreign_keys="[ChatWidgetMember.tenant_id, ChatWidgetMember.principal_id]",
        primaryjoin="and_(ChatWidgetMember.tenant_id == Principal.tenant_id, ChatWidgetMember.principal_id == Principal.principal_id)"
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "principal_id"],
            ["principals.tenant_id", "principals.principal_id"],
            ondelete="CASCADE",
            name="fk_chat_widget_members_principal"
        ),
        UniqueConstraint("chat_widget_id", "principal_id", name="uq_chat_widget_members"),
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
    tool_tags: Mapped[list["ToolTag"]] = relationship(
        back_populates="tag", cascade="all, delete-orphan"
    )

    @validates('name')
    def convert_upper(self, key, value):
        """Convert tag name to uppercase."""
        return value.upper() if value else value

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_tag_tenant_name"),
        Index("ix_tags_tenant", "tenant_id"),
        Index("ix_tags_name", "name"),
    )


class ApplicationTag(Base, AuditMixin):
    """Junction table for application tags."""
    __tablename__ = "application_tags"

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, primary_key=True)
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )

    tag: Mapped["Tag"] = relationship(back_populates="application_tags")
    application: Mapped["Application"] = relationship(back_populates="tags")

    __table_args__ = (
        Index("ix_at_application", "application_id"),
        Index("ix_at_tag", "tag_id"),
    )


class AutonomousAgentTag(Base, AuditMixin):
    """Junction table for autonomous agent tags."""
    __tablename__ = "autonomous_agent_tags"

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, primary_key=True)
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    autonomous_agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("autonomous_agents.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )

    tag: Mapped["Tag"] = relationship(back_populates="autonomous_agent_tags")
    autonomous_agent: Mapped["AutonomousAgent"] = relationship(back_populates="tags")

    __table_args__ = (
        Index("ix_aat_autonomous_agent", "autonomous_agent_id"),
        Index("ix_aat_tag", "tag_id"),
    )


class ChatWidgetTag(Base, AuditMixin):
    """Junction table for chat widget tags."""
    __tablename__ = "chat_widget_tags"

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, primary_key=True)
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    chat_widget_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_widgets.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )

    tag: Mapped["Tag"] = relationship(back_populates="chat_widget_tags")
    chat_widget: Mapped["ChatWidget"] = relationship(back_populates="tags")

    __table_args__ = (
        Index("ix_cwt_chat_widget", "chat_widget_id"),
        Index("ix_cwt_tag", "tag_id"),
    )


class CredentialTag(Base, AuditMixin):
    """Junction table for credential tags."""
    __tablename__ = "credential_tags"

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, primary_key=True)
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    credential_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("credentials.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )

    tag: Mapped["Tag"] = relationship(back_populates="credential_tags")
    credential: Mapped["Credential"] = relationship(back_populates="tags")

    __table_args__ = (
        Index("ix_crt_credential", "credential_id"),
        Index("ix_crt_tag", "tag_id"),
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
        String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )

    application: Mapped["Application"] = relationship(back_populates="user_favorites")
    principal: Mapped["Principal"] = relationship(
        foreign_keys="[ApplicationUserFavorite.tenant_id, ApplicationUserFavorite.user_id]",
        primaryjoin="and_(ApplicationUserFavorite.tenant_id == Principal.tenant_id, ApplicationUserFavorite.user_id == Principal.principal_id)"
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["principals.tenant_id", "principals.principal_id"],
            ondelete="CASCADE",
            name="fk_application_user_favorites_principal"
        ),
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
        String(36), ForeignKey("autonomous_agents.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )

    autonomous_agent: Mapped["AutonomousAgent"] = relationship(back_populates="user_favorites")
    principal: Mapped["Principal"] = relationship(
        foreign_keys="[AutonomousAgentUserFavorite.tenant_id, AutonomousAgentUserFavorite.user_id]",
        primaryjoin="and_(AutonomousAgentUserFavorite.tenant_id == Principal.tenant_id, AutonomousAgentUserFavorite.user_id == Principal.principal_id)"
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["principals.tenant_id", "principals.principal_id"],
            ondelete="CASCADE",
            name="fk_autonomous_agent_user_favorites_principal"
        ),
        Index("ix_aauf_user", "user_id"),
        Index("ix_aauf_autonomous_agent", "autonomous_agent_id"),
    )


class ConversationUserFavorite(Base, AuditMixin):
    """User favorites for conversations."""
    __tablename__ = "conversation_user_favorites"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    user_id: Mapped[str] = mapped_column(String(50), nullable=False, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="user_favorites")
    principal: Mapped["Principal"] = relationship(
        foreign_keys="[ConversationUserFavorite.tenant_id, ConversationUserFavorite.user_id]",
        primaryjoin="and_(ConversationUserFavorite.tenant_id == Principal.tenant_id, ConversationUserFavorite.user_id == Principal.principal_id)"
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["principals.tenant_id", "principals.principal_id"],
            ondelete="CASCADE",
            name="fk_conversation_user_favorites_principal"
        ),
        Index("ix_cuf_user", "user_id"),
        Index("ix_cuf_conversation", "conversation_id"),
    )


# ---------- Tools (ReACT Agent Tools) ----------
class Tool(Base, IdNameDescriptionMixin, TenantScopedMixin):
    """Tool entity for ReACT agent tools (MCP servers, OpenAPI definitions)."""
    __tablename__ = "tools"

    type: Mapped[str] = mapped_column(String(50), nullable=False)
    config: Mapped[dict] = mapped_column(PortableJSON, nullable=False, default=dict)
    credential_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("credentials.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    credential: Mapped[Optional["Credential"]] = relationship(foreign_keys=[credential_id])
    members: Mapped[list["ToolMember"]] = relationship(
        back_populates="tool", cascade="all, delete-orphan"
    )
    tags: Mapped[list["ToolTag"]] = relationship(
        back_populates="tool", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_tools_tenant", "tenant_id"),)


class TenantAIModel(Base, IdNameDescriptionMixin, TenantScopedMixin):
    """Tenant AI model entity for LLM and embedding model configurations."""
    __tablename__ = "tenant_ai_models"

    type: Mapped[str] = mapped_column(AIModelTypeSAEnum, nullable=False)
    provider: Mapped[str] = mapped_column(AIModelProviderSAEnum, nullable=False)
    purpose_groups: Mapped[list] = mapped_column(PortableJSON, nullable=False, default=list)
    config: Mapped[dict] = mapped_column(PortableJSON, nullable=False, default=dict)
    credential_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("credentials.id", ondelete="SET NULL"), nullable=True
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    credential: Mapped[Optional["Credential"]] = relationship(foreign_keys=[credential_id])

    __table_args__ = (Index("ix_tenant_ai_models_tenant", "tenant_id"),)


class ToolMember(Base, IdMixin, AuditMixin):
    """Tool membership table."""
    __tablename__ = "tool_members"

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    tool_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tools.id", ondelete="CASCADE"), nullable=False
    )
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)

    role: Mapped[str] = mapped_column(PermissionActionSAEnum, nullable=False)

    tool: Mapped["Tool"] = relationship(back_populates="members")
    principal: Mapped["Principal"] = relationship(
        foreign_keys="[ToolMember.tenant_id, ToolMember.principal_id]",
        primaryjoin="and_(ToolMember.tenant_id == Principal.tenant_id, ToolMember.principal_id == Principal.principal_id)"
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "principal_id"],
            ["principals.tenant_id", "principals.principal_id"],
            ondelete="CASCADE",
            name="fk_tool_members_principal"
        ),
        UniqueConstraint("tool_id", "principal_id", name="uq_tool_members"),
        Index("ix_tool_members_tool", "tool_id"),
        Index("ix_tool_members_principal", "principal_id"),
    )


class ToolTag(Base, AuditMixin):
    """Junction table for tool tags."""
    __tablename__ = "tool_tags"

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, primary_key=True)
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    tool_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tools.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )

    tag: Mapped["Tag"] = relationship(back_populates="tool_tags")
    tool: Mapped["Tool"] = relationship(back_populates="tags")

    __table_args__ = (
        Index("ix_tt_tool", "tool_id"),
        Index("ix_tt_tag", "tag_id"),
    )


