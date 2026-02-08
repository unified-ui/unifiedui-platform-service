# Database

## ORM
SQLAlchemy with declarative models in `unifiedui/core/database/models.py`.

---

## Enums (`core/database/enums.py`)

### TenantRolesEnum
Tenant-level roles that can be assigned to tenant members:
- `READER` — View-only access to the tenant
- `GLOBAL_ADMIN` — Full access to everything
- `{RESOURCE}_ADMIN` — Full access to specific resource type (e.g., `APPLICATIONS_ADMIN`)
- `{RESOURCE}_CREATOR` — Can create new instances of resource type (e.g., `APPLICATIONS_CREATOR`)

Supported resources: applications, credentials, conversations, autonomous_agents, chat_widgets, custom_groups, react_agent (tools), tenant_ai_models

### PermissionActionEnum
Resource-level roles (one per member entry in `{resource}_members` table):
- `READ` — View the resource
- `WRITE` — Modify the resource (implies READ)
- `ADMIN` — Full control + manage permissions (implies WRITE + READ)

Hierarchy: **ADMIN > WRITE > READ**

### PrincipalTypeEnum
Who can receive permissions:
- `IDENTITY_USER` — Individual user from identity provider
- `IDENTITY_GROUP` — Group from identity provider (Azure AD)
- `CUSTOM_GROUP` — Custom group defined within unifiedui

### Other Enums
- `ApplicationTypeEnum`: `N8N`, `MICROSOFT_FOUNDRY`, `REST_API`
- `AutonomousAgentTypeEnum`: `N8N`
- `ChatWidgetTypeEnum`: `IFRAME`, `FORM`
- `ToolTypeEnum`: `MCP_SERVER`, `OPENAPI_DEFINITION`
- `AIModelTypeEnum`: `LLM_MODEL`, `EMBEDDING_MODEL`
- `AIModelProviderEnum`: `AZURE_OPENAI`, `OPENAI`, `ANTHROPIC`, `GOOGLE_GENAI`, `OLLAMA`, `MISTRAL`, `GROQ`
- `AIModelPurposeGroupEnum`: `CONVERSATION_TITLE_GENERATION`, `CONVERSATION_SUMMARIZATION`, `DESCRIPTION_GENERATION`, `TRACE_ANALYSIS`, `GENERAL`
- `UserPermissionEnum`: `IS_CREATOR` (special — used for tag/favorite ownership)
- `OrderDirectionEnum`: `asc`, `desc`
- `ListViewEnum`: `full`, `quick-list`

---

## Model Pattern

### Base Mixins
- `IdMixin` — Adds `id: str` (UUID, auto-generated)
- `AuditMixin` — Adds `created_at`, `updated_at`, `created_by`, `updated_by`
- `TenantScopedMixin` — Adds `tenant_id: str` (FK to tenants)
- `IdNameDescriptionMixin` — Combines `IdMixin` + name + description fields

### Custom Column Types
- `PortableJSON` — JSON column that works across PostgreSQL (native JSONB) and SQLite (JSON string)
- `HighPrecisionDateTime` — DateTime ensuring microsecond precision across databases

### Standard Resource Model

```python
class Application(Base, IdNameDescriptionMixin, TenantScopedMixin):
    """Application entity model."""
    __tablename__ = "applications"
    
    type: Mapped[str] = mapped_column(...)
    config: Mapped[dict] = mapped_column(PortableJSON, default=dict)
    is_active: Mapped[bool] = mapped_column(default=False)
    
    # Audit fields
    created_at: Mapped[datetime] = ...
    updated_at: Mapped[datetime] = ...
    created_by: Mapped[str] = ...
    updated_by: Mapped[str] = ...
    
    # Relationships
    members: Mapped[list["ApplicationMember"]] = relationship(...)
    tags: Mapped[list["ApplicationTag"]] = relationship(...)
```

### Standard Member Model (RBAC)

```python
class ApplicationMember(Base, IdMixin, AuditMixin):
    """Application member/permission model."""
    __tablename__ = "application_members"
    
    tenant_id: Mapped[str] = mapped_column(...)
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE")
    )
    principal_id: Mapped[str] = mapped_column(String(50))
    principal_type: Mapped[str] = mapped_column(PrincipalTypeSAEnum)
    role: Mapped[str] = mapped_column(PermissionActionSAEnum)  # READ | WRITE | ADMIN
    
    # Unique constraint: one role per principal per resource
    __table_args__ = (
        UniqueConstraint("application_id", "principal_id", "principal_type", "role"),
    )
```

---

## All Resource Entities

| Entity | Member Table | Config Validator | Tags Support |
|--------|-------------|-----------------|--------------|
| Tenant | TenantMember + TenantMemberRole | — | No |
| Application | ApplicationMember | ApplicationConfigValidatorFactory | Yes |
| Credential | CredentialMember | CredentialValidator | Yes |
| AutonomousAgent | AutonomousAgentMember | AutonomousAgentConfigValidator | Yes |
| Conversation | ConversationMember | — | No |
| ChatWidget | ChatWidgetMember | — | Yes |
| CustomGroup | CustomGroupMember | — | No |
| Tool | ToolMember | ToolValidator | No |
| TenantAIModel | — (no RBAC, S2S-only via `@authenticate_service_key`) | TenantAIModelValidator | No |
| Tag | — (uses `created_by` for ownership) | — | N/A |
| UserFavorite | — (scoped by user_id) | — | No |

---

## Tenant Special Case

Tenants use a **different permission model**:
- `TenantMember` — Links user/group to tenant
- `TenantMemberRole` — Supports **multiple roles per member** (e.g., `READER` + `APPLICATIONS_CREATOR`)
- Uses `TenantRolesEnum` (not `PermissionActionEnum`)

---

## SQLAlchemy Client

`core/database/client.py` provides `SQLAlchemyClient`:

```python
with db_client.get_session() as session:
    result = session.execute(select(Application).where(...))
    app = result.scalar_one_or_none()
```

- Sessions are context-managed (auto-commit on exit, rollback on exception)
- Function-scoped in tests (SQLite temp file per test)

---

## Migrations

Using Alembic:
```bash
alembic revision --autogenerate -m "add new column"
alembic upgrade head
alembic downgrade -1
```

- Config in `alembic.ini`
- Migration env in `alembic/env.py`
- Always test migrations in both directions (up/down)
