from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Sequence,
    String,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects import mssql, postgresql
from sqlalchemy.dialects.postgresql import TIMESTAMP as PG_TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, validates
from sqlalchemy.types import JSON, TypeDecorator

from unifiedui.core.database.enums import (
    AIModelProviderEnum,
    AIModelTypeEnum,
    AutonomousAgentTypeEnum,
    ChatAgentTypeEnum,
    EnvironmentTypeEnum,
    OrganizationRoleEnum,
    PermissionActionEnum,
    PrincipalTypeEnum,
    TenantRolesEnum,
)


# ---------- Utility functions ----------
def utc_now() -> datetime:
    """Return current UTC time with microsecond precision."""
    return datetime.now(UTC)


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

ChatAgentTypeSAEnum = SAEnum(
    *ChatAgentTypeEnum.all(),
    name="chat_agent_type",
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

OrganizationRoleSAEnum = SAEnum(
    *OrganizationRoleEnum.all(),
    name="organization_role",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)

EnvironmentTypeSAEnum = SAEnum(
    *EnvironmentTypeEnum.all(),
    name="environment_type",
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

    created_at: Mapped[datetime] = mapped_column(HighPrecisionDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        HighPrecisionDateTime(), nullable=False, default=utc_now, onupdate=utc_now
    )
    created_by: Mapped[str | None] = mapped_column(String(50))
    updated_by: Mapped[str | None] = mapped_column(String(50))


class IdNameDescriptionMixin(IdMixin, AuditMixin):
    """Mixin for entities with ID, name, description and audit fields."""

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000))


class TenantScopedMixin:
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)


# ---------- Organization ----------
class Organization(Base, IdMixin, AuditMixin):
    """Organization entity representing a company or customer."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000))

    identity_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    identity_tenant_id: Mapped[str] = mapped_column(String(255), nullable=False)

    subscription_tier: Mapped[str] = mapped_column(String(50), nullable=False, default="free")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    members: Mapped[list[OrganizationMember]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    tenants: Mapped[list[Tenant]] = relationship(back_populates="organization", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("identity_provider", "identity_tenant_id", name="uq_org_idp"),
        Index("ix_org_slug", "slug"),
        Index("ix_org_idp", "identity_provider", "identity_tenant_id"),
    )


class OrganizationMember(Base, IdMixin, AuditMixin):
    """Organization membership and roles."""

    __tablename__ = "organization_members"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)
    principal_type: Mapped[str] = mapped_column(PrincipalTypeSAEnum, nullable=False)
    role: Mapped[str] = mapped_column(OrganizationRoleSAEnum, nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="members")

    __table_args__ = (
        UniqueConstraint("organization_id", "principal_id", "role", name="uq_org_member"),
        Index("ix_org_member_org", "organization_id"),
        Index("ix_org_member_principal", "principal_id"),
    )


# ---------- Core ----------
class Tenant(Base, IdNameDescriptionMixin):
    """Tenant entity representing an environment within an organization."""

    __tablename__ = "tenants"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    environment_type: Mapped[str] = mapped_column(
        EnvironmentTypeSAEnum, nullable=False, default=EnvironmentTypeEnum.SANDBOX.value
    )
    previous_stage_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_be_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    organization: Mapped[Organization] = relationship(back_populates="tenants")
    members: Mapped[list[TenantMember]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    principals: Mapped[list[Principal]] = relationship(back_populates="tenant", cascade="all, delete-orphan")


class TenantMember(Base, IdMixin, AuditMixin):
    """
    Tenant membership and roles.
    Links directly to Principals via (tenant_id, principal_id).
    """

    __tablename__ = "tenant_members"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)
    role: Mapped[str] = mapped_column(TenantPermissionSAEnum, nullable=False)

    tenant: Mapped[Tenant] = relationship(back_populates="members")
    principal: Mapped[Principal] = relationship(
        foreign_keys="[TenantMember.tenant_id, TenantMember.principal_id]",
        primaryjoin="and_(TenantMember.tenant_id == Principal.tenant_id, TenantMember.principal_id == Principal.principal_id)",
        overlaps="members,tenant",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "principal_id"],
            ["principals.tenant_id", "principals.principal_id"],
            ondelete="CASCADE",
            name="fk_tenant_members_principal",
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
    mail: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    principal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(HighPrecisionDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        HighPrecisionDateTime(), nullable=False, default=utc_now, onupdate=utc_now
    )

    # Relationships
    tenant: Mapped[Tenant] = relationship(back_populates="principals")
    custom_group_members: Mapped[list[CustomGroupMember]] = relationship(
        back_populates="custom_group",
        foreign_keys="[CustomGroupMember.tenant_id, CustomGroupMember.custom_group_id]",
        primaryjoin="and_(Principal.tenant_id == CustomGroupMember.tenant_id, Principal.principal_id == CustomGroupMember.custom_group_id)",
        cascade="all, delete-orphan",
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

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    custom_group_id: Mapped[str] = mapped_column(String(50), nullable=False)
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)
    role: Mapped[str] = mapped_column(PermissionActionSAEnum, nullable=False)

    # Relationships
    custom_group: Mapped[Principal] = relationship(
        back_populates="custom_group_members",
        foreign_keys="[CustomGroupMember.tenant_id, CustomGroupMember.custom_group_id]",
        primaryjoin="and_(CustomGroupMember.tenant_id == Principal.tenant_id, CustomGroupMember.custom_group_id == Principal.principal_id)",
    )
    member_principal: Mapped[Principal] = relationship(
        foreign_keys="[CustomGroupMember.tenant_id, CustomGroupMember.principal_id]",
        primaryjoin="and_(CustomGroupMember.tenant_id == Principal.tenant_id, CustomGroupMember.principal_id == Principal.principal_id)",
        overlaps="custom_group,custom_group_members",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "custom_group_id"],
            ["principals.tenant_id", "principals.principal_id"],
            ondelete="CASCADE",
            name="fk_custom_group_members_custom_group",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "principal_id"],
            ["principals.tenant_id", "principals.principal_id"],
            ondelete="CASCADE",
            name="fk_custom_group_members_principal",
        ),
        UniqueConstraint("tenant_id", "custom_group_id", "principal_id", name="uq_custom_group_members"),
        Index("ix_cgm_tenant", "tenant_id"),
        Index("ix_cgm_custom_group", "custom_group_id"),
        Index("ix_cgm_principal", "principal_id"),
    )


class ChatAgent(Base, IdNameDescriptionMixin, TenantScopedMixin):
    """Chat agent entity for AI-powered chat integrations."""

    __tablename__ = "chat_agents"

    type: Mapped[str] = mapped_column(ChatAgentTypeSAEnum, nullable=False)
    config: Mapped[dict] = mapped_column(PortableJSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    embed_allowed_origins: Mapped[str | None] = mapped_column(String(2000), nullable=True, default=None)

    members: Mapped[list[ChatAgentMember]] = relationship(back_populates="chat_agent", cascade="all, delete-orphan")
    tags: Mapped[list[ChatAgentTag]] = relationship(back_populates="chat_agent", cascade="all, delete-orphan")
    user_favorites: Mapped[list[ChatAgentUserFavorite]] = relationship(
        back_populates="chat_agent", cascade="all, delete-orphan"
    )
    versions: Mapped[list[ReActAgentVersion]] = relationship(
        back_populates="chat_agent", cascade="all, delete-orphan", order_by="ReActAgentVersion.version.desc()"
    )

    __table_args__ = (Index("ix_chat_agents_tenant", "tenant_id"),)


class Conversation(Base, IdNameDescriptionMixin, TenantScopedMixin):
    __tablename__ = "conversations"

    chat_agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_agents.id", ondelete="CASCADE"), nullable=False
    )
    ext_conversation_id: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    chat_agent: Mapped[ChatAgent] = relationship()
    members: Mapped[list[ConversationMember]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    user_favorites: Mapped[list[ConversationUserFavorite]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_conversations_tenant", "tenant_id"),
        Index("ix_conversations_chat_agent", "chat_agent_id"),
    )


class AutonomousAgent(Base, IdNameDescriptionMixin, TenantScopedMixin):
    __tablename__ = "autonomous_agents"

    type: Mapped[str] = mapped_column(AutonomousAgentTypeSAEnum, nullable=False)
    config: Mapped[dict] = mapped_column(PortableJSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_api_keys: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    primary_key_vault_uri: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    secondary_key_vault_uri: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    last_full_import: Mapped[datetime | None] = mapped_column(HighPrecisionDateTime(), nullable=True, default=None)

    members: Mapped[list[AutonomousAgentMember]] = relationship(
        back_populates="autonomous_agent", cascade="all, delete-orphan"
    )
    tags: Mapped[list[AutonomousAgentTag]] = relationship(
        back_populates="autonomous_agent", cascade="all, delete-orphan"
    )
    user_favorites: Mapped[list[AutonomousAgentUserFavorite]] = relationship(
        back_populates="autonomous_agent", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_autonomous_agents_tenant", "tenant_id"),)


class Credential(Base, IdNameDescriptionMixin, TenantScopedMixin):
    __tablename__ = "credentials"

    type: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    credential_uri: Mapped[str] = mapped_column(String(2000), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    members: Mapped[list[CredentialMember]] = relationship(back_populates="credential", cascade="all, delete-orphan")
    tags: Mapped[list[CredentialTag]] = relationship(back_populates="credential", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_credentials_tenant", "tenant_id"),)


# ---------- Permission tables ----------
class ChatAgentMember(Base, IdMixin, AuditMixin):
    """Chat agent membership table."""

    __tablename__ = "chat_agent_members"

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    chat_agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_agents.id", ondelete="CASCADE"), nullable=False
    )
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)

    role: Mapped[str] = mapped_column(PermissionActionSAEnum, nullable=False)

    chat_agent: Mapped[ChatAgent] = relationship(back_populates="members")
    principal: Mapped[Principal] = relationship(
        foreign_keys="[ChatAgentMember.tenant_id, ChatAgentMember.principal_id]",
        primaryjoin="and_(ChatAgentMember.tenant_id == Principal.tenant_id, ChatAgentMember.principal_id == Principal.principal_id)",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "principal_id"],
            ["principals.tenant_id", "principals.principal_id"],
            ondelete="CASCADE",
            name="fk_chat_agent_members_principal",
        ),
        UniqueConstraint("chat_agent_id", "principal_id", name="uq_chat_agent_members"),
        Index("ix_cam_chat_agent", "chat_agent_id"),
        Index("ix_cam_principal", "principal_id"),
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

    conversation: Mapped[Conversation] = relationship(back_populates="members")
    principal: Mapped[Principal] = relationship(
        foreign_keys="[ConversationMember.tenant_id, ConversationMember.principal_id]",
        primaryjoin="and_(ConversationMember.tenant_id == Principal.tenant_id, ConversationMember.principal_id == Principal.principal_id)",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "principal_id"],
            ["principals.tenant_id", "principals.principal_id"],
            ondelete="CASCADE",
            name="fk_conversation_members_principal",
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

    autonomous_agent: Mapped[AutonomousAgent] = relationship(back_populates="members")
    principal: Mapped[Principal] = relationship(
        foreign_keys="[AutonomousAgentMember.tenant_id, AutonomousAgentMember.principal_id]",
        primaryjoin="and_(AutonomousAgentMember.tenant_id == Principal.tenant_id, AutonomousAgentMember.principal_id == Principal.principal_id)",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "principal_id"],
            ["principals.tenant_id", "principals.principal_id"],
            ondelete="CASCADE",
            name="fk_autonomous_agent_members_principal",
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

    credential: Mapped[Credential] = relationship(back_populates="members")
    principal: Mapped[Principal] = relationship(
        foreign_keys="[CredentialMember.tenant_id, CredentialMember.principal_id]",
        primaryjoin="and_(CredentialMember.tenant_id == Principal.tenant_id, CredentialMember.principal_id == Principal.principal_id)",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "principal_id"],
            ["principals.tenant_id", "principals.principal_id"],
            ondelete="CASCADE",
            name="fk_credential_members_principal",
        ),
        UniqueConstraint("credential_id", "principal_id", name="uq_credential_members"),
        Index("ix_crm_credential", "credential_id"),
        Index("ix_crm_principal", "principal_id"),
    )


# ---------- Chat Widgets ----------
class ChatWidget(Base, IdNameDescriptionMixin, TenantScopedMixin):
    """Chat widget entity for embedding chat interfaces."""

    __tablename__ = "chat_widgets"

    type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    config: Mapped[dict] = mapped_column(PortableJSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    members: Mapped[list[ChatWidgetMember]] = relationship(back_populates="chat_widget", cascade="all, delete-orphan")
    tags: Mapped[list[ChatWidgetTag]] = relationship(back_populates="chat_widget", cascade="all, delete-orphan")
    user_favorites: Mapped[list[ChatWidgetUserFavorite]] = relationship(
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

    chat_widget: Mapped[ChatWidget] = relationship(back_populates="members")
    principal: Mapped[Principal] = relationship(
        foreign_keys="[ChatWidgetMember.tenant_id, ChatWidgetMember.principal_id]",
        primaryjoin="and_(ChatWidgetMember.tenant_id == Principal.tenant_id, ChatWidgetMember.principal_id == Principal.principal_id)",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "principal_id"],
            ["principals.tenant_id", "principals.principal_id"],
            ondelete="CASCADE",
            name="fk_chat_widget_members_principal",
        ),
        UniqueConstraint("chat_widget_id", "principal_id", name="uq_chat_widget_members"),
        Index("ix_cwm_chat_widget", "chat_widget_id"),
        Index("ix_cwm_principal", "principal_id"),
    )


# ---------- Tags ----------
# Sequence for auto-incrementing tag IDs starting at 10000 (PostgreSQL only)
# SQLite will use AUTOINCREMENT instead
tag_id_seq = Sequence("tag_id_seq", start=10000, optional=True)


class Tag(Base, AuditMixin):
    """Tag entity for categorizing resources."""

    __tablename__ = "tags"

    # Note: For PostgreSQL, the sequence starts at 10000
    # For SQLite (tests), it starts at 1 (standard autoincrement)
    id: Mapped[int] = mapped_column(Integer, tag_id_seq, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships to junction tables
    chat_agent_tags: Mapped[list[ChatAgentTag]] = relationship(back_populates="tag", cascade="all, delete-orphan")
    autonomous_agent_tags: Mapped[list[AutonomousAgentTag]] = relationship(
        back_populates="tag", cascade="all, delete-orphan"
    )
    chat_widget_tags: Mapped[list[ChatWidgetTag]] = relationship(back_populates="tag", cascade="all, delete-orphan")
    credential_tags: Mapped[list[CredentialTag]] = relationship(back_populates="tag", cascade="all, delete-orphan")
    tool_tags: Mapped[list[ToolTag]] = relationship(back_populates="tag", cascade="all, delete-orphan")

    @validates("name")
    def convert_upper(self, key, value):
        """Convert tag name to uppercase."""
        return value.upper() if value else value

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_tag_tenant_name"),
        Index("ix_tags_tenant", "tenant_id"),
        Index("ix_tags_name", "name"),
    )


class ChatAgentTag(Base, AuditMixin):
    """Junction table for chat agent tags."""

    __tablename__ = "chat_agent_tags"

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, primary_key=True)
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    chat_agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_agents.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )

    tag: Mapped[Tag] = relationship(back_populates="chat_agent_tags")
    chat_agent: Mapped[ChatAgent] = relationship(back_populates="tags")

    __table_args__ = (
        Index("ix_cat_chat_agent", "chat_agent_id"),
        Index("ix_cat_tag", "tag_id"),
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

    tag: Mapped[Tag] = relationship(back_populates="autonomous_agent_tags")
    autonomous_agent: Mapped[AutonomousAgent] = relationship(back_populates="tags")

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

    tag: Mapped[Tag] = relationship(back_populates="chat_widget_tags")
    chat_widget: Mapped[ChatWidget] = relationship(back_populates="tags")

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

    tag: Mapped[Tag] = relationship(back_populates="credential_tags")
    credential: Mapped[Credential] = relationship(back_populates="tags")

    __table_args__ = (
        Index("ix_crt_credential", "credential_id"),
        Index("ix_crt_tag", "tag_id"),
    )


# ---------- User Favorites ----------
class ChatAgentUserFavorite(Base, AuditMixin):
    """User favorites for chat agents."""

    __tablename__ = "chat_agent_user_favorites"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    user_id: Mapped[str] = mapped_column(String(50), nullable=False, primary_key=True)
    chat_agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_agents.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )

    chat_agent: Mapped[ChatAgent] = relationship(back_populates="user_favorites")
    principal: Mapped[Principal] = relationship(
        foreign_keys="[ChatAgentUserFavorite.tenant_id, ChatAgentUserFavorite.user_id]",
        primaryjoin="and_(ChatAgentUserFavorite.tenant_id == Principal.tenant_id, ChatAgentUserFavorite.user_id == Principal.principal_id)",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["principals.tenant_id", "principals.principal_id"],
            ondelete="CASCADE",
            name="fk_chat_agent_user_favorites_principal",
        ),
        Index("ix_cauf_user", "user_id"),
        Index("ix_cauf_chat_agent", "chat_agent_id"),
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

    autonomous_agent: Mapped[AutonomousAgent] = relationship(back_populates="user_favorites")
    principal: Mapped[Principal] = relationship(
        foreign_keys="[AutonomousAgentUserFavorite.tenant_id, AutonomousAgentUserFavorite.user_id]",
        primaryjoin="and_(AutonomousAgentUserFavorite.tenant_id == Principal.tenant_id, AutonomousAgentUserFavorite.user_id == Principal.principal_id)",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["principals.tenant_id", "principals.principal_id"],
            ondelete="CASCADE",
            name="fk_autonomous_agent_user_favorites_principal",
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

    conversation: Mapped[Conversation] = relationship(back_populates="user_favorites")
    principal: Mapped[Principal] = relationship(
        foreign_keys="[ConversationUserFavorite.tenant_id, ConversationUserFavorite.user_id]",
        primaryjoin="and_(ConversationUserFavorite.tenant_id == Principal.tenant_id, ConversationUserFavorite.user_id == Principal.principal_id)",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["principals.tenant_id", "principals.principal_id"],
            ondelete="CASCADE",
            name="fk_conversation_user_favorites_principal",
        ),
        Index("ix_cuf_user", "user_id"),
        Index("ix_cuf_conversation", "conversation_id"),
    )


class ChatWidgetUserFavorite(Base, AuditMixin):
    """User favorites for chat widgets."""

    __tablename__ = "chat_widget_user_favorites"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    user_id: Mapped[str] = mapped_column(String(50), nullable=False, primary_key=True)
    chat_widget_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_widgets.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )

    chat_widget: Mapped[ChatWidget] = relationship(back_populates="user_favorites")
    principal: Mapped[Principal] = relationship(
        foreign_keys="[ChatWidgetUserFavorite.tenant_id, ChatWidgetUserFavorite.user_id]",
        primaryjoin="and_(ChatWidgetUserFavorite.tenant_id == Principal.tenant_id, ChatWidgetUserFavorite.user_id == Principal.principal_id)",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["principals.tenant_id", "principals.principal_id"],
            ondelete="CASCADE",
            name="fk_chat_widget_user_favorites_principal",
        ),
        Index("ix_cwuf_user", "user_id"),
        Index("ix_cwuf_chat_widget", "chat_widget_id"),
    )


# ---------- Tools (ReACT Agent Tools) ----------
class Tool(Base, IdNameDescriptionMixin, TenantScopedMixin):
    """Tool entity for ReACT agent tools (MCP servers, OpenAPI definitions)."""

    __tablename__ = "tools"

    type: Mapped[str] = mapped_column(String(50), nullable=False)
    config: Mapped[dict] = mapped_column(PortableJSON, nullable=False, default=dict)
    credential_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("credentials.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    credential: Mapped[Credential | None] = relationship(foreign_keys=[credential_id])
    members: Mapped[list[ToolMember]] = relationship(back_populates="tool", cascade="all, delete-orphan")
    tags: Mapped[list[ToolTag]] = relationship(back_populates="tool", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_tools_tenant", "tenant_id"),)


class TenantAIModel(Base, IdNameDescriptionMixin, TenantScopedMixin):
    """Tenant AI model entity for LLM and embedding model configurations."""

    __tablename__ = "tenant_ai_models"

    type: Mapped[str] = mapped_column(AIModelTypeSAEnum, nullable=False)
    provider: Mapped[str] = mapped_column(AIModelProviderSAEnum, nullable=False)
    purpose_groups: Mapped[list] = mapped_column(PortableJSON, nullable=False, default=list)
    config: Mapped[dict] = mapped_column(PortableJSON, nullable=False, default=dict)
    credential_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("credentials.id", ondelete="SET NULL"), nullable=True
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    credential: Mapped[Credential | None] = relationship(foreign_keys=[credential_id])

    __table_args__ = (Index("ix_tenant_ai_models_tenant", "tenant_id"),)


class ToolMember(Base, IdMixin, AuditMixin):
    """Tool membership table."""

    __tablename__ = "tool_members"

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    tool_id: Mapped[str] = mapped_column(String(36), ForeignKey("tools.id", ondelete="CASCADE"), nullable=False)
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)

    role: Mapped[str] = mapped_column(PermissionActionSAEnum, nullable=False)

    tool: Mapped[Tool] = relationship(back_populates="members")
    principal: Mapped[Principal] = relationship(
        foreign_keys="[ToolMember.tenant_id, ToolMember.principal_id]",
        primaryjoin="and_(ToolMember.tenant_id == Principal.tenant_id, ToolMember.principal_id == Principal.principal_id)",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "principal_id"],
            ["principals.tenant_id", "principals.principal_id"],
            ondelete="CASCADE",
            name="fk_tool_members_principal",
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

    tag: Mapped[Tag] = relationship(back_populates="tool_tags")
    tool: Mapped[Tool] = relationship(back_populates="tags")

    __table_args__ = (
        Index("ix_tt_tool", "tool_id"),
        Index("ix_tt_tag", "tag_id"),
    )


# ---------- ReACT Agent Versions (linked to ChatAgent) ----------
class ReActAgentVersion(Base, IdMixin, AuditMixin):
    """Versioned configuration for a ReACT Agent (chat_agent with type=REACT_AGENT)."""

    __tablename__ = "re_act_agent_versions"

    chat_agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_agents.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    ai_model_ids: Mapped[list] = mapped_column(PortableJSON, nullable=False, default=list)
    system_prompt: Mapped[str | None] = mapped_column(String(8000), nullable=True)
    tool_ids: Mapped[list] = mapped_column(PortableJSON, nullable=False, default=list)
    security_prompt: Mapped[str | None] = mapped_column(String(8000), nullable=True)
    tool_use_prompt: Mapped[str | None] = mapped_column(String(8000), nullable=True)
    response_prompt: Mapped[str | None] = mapped_column(String(8000), nullable=True)
    greeting_messages: Mapped[list] = mapped_column(PortableJSON, nullable=False, default=list)
    config: Mapped[dict] = mapped_column(PortableJSON, nullable=False, default=dict)

    chat_agent: Mapped[ChatAgent] = relationship(back_populates="versions")

    __table_args__ = (
        UniqueConstraint("chat_agent_id", "version", name="uq_re_act_agent_version"),
        Index("ix_re_act_agent_versions_agent", "chat_agent_id"),
        Index("ix_re_act_agent_versions_agent_version", "chat_agent_id", "version"),
    )


# ---------- Recent Visits ----------
class RecentVisit(Base, IdMixin, TenantScopedMixin):
    """Recent visit tracking for users."""

    __tablename__ = "recent_visits"

    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(36), nullable=False)
    resource_name: Mapped[str] = mapped_column(String(255), nullable=False)
    visited_at: Mapped[datetime] = mapped_column(HighPrecisionDateTime(), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "resource_type", "resource_id", name="uq_recent_visits"),
        Index("ix_recent_visits_user_time", "tenant_id", "user_id", "visited_at"),
    )
