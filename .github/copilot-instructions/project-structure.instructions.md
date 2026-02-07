# Project Structure

## Folder Overview

```
unified-ui-platform-service/
├── alembic/                    # Database migrations
│   ├── env.py
│   └── versions/               # Migration files
├── tests/                      # All tests → see testing.instructions.md
│   ├── conftest.py             # Root conftest (imports all fixtures)
│   ├── fixtures/               # Shared test fixtures
│   │   ├── auth.py             # MockIdentityToken, create_auth_headers
│   │   ├── cache.py            # fakeredis, test_cache_client
│   │   ├── client.py           # FastAPI TestClient fixture
│   │   ├── data.py             # Sample tenant/resource data
│   │   ├── database.py         # SQLite test engine + session
│   │   └── vault.py            # MockVault in-memory implementation
│   └── unit/
│       ├── api/v1/             # API route tests (3-file pattern per resource)
│       ├── handlers/           # Handler unit tests
│       ├── caching/            # Cache infrastructure tests
│       ├── core/               # Core module tests (middleware, identity, vault)
│       ├── identity/           # Identity provider tests
│       ├── libs/               # Library tests
│       ├── schema/             # Schema validation tests
│       ├── utils/              # Utility tests
│       └── vault/              # Vault implementation tests
├── unifiedui/                  # Main application package
│   ├── app.py                  # FastAPI app factory + exception handlers
│   ├── logger.py               # Centralized logging setup
│   ├── apis/v1/                # API route definitions (thin wrappers)
│   ├── handlers/               # Business logic (ALL logic here)
│   │   ├── dependencies/       # FastAPI Depends() factories
│   │   └── validators/         # Config/credential validators
│   ├── schema/                 # Pydantic models
│   │   ├── requests/           # Request body schemas
│   │   └── responses/          # Response body schemas
│   ├── core/                   # Interfaces + base implementations
│   │   ├── config.py           # Settings (pydantic-settings, env vars)
│   │   ├── security.py         # Security utilities
│   │   ├── database/           # DB models, enums, client interface
│   │   │   ├── models.py       # SQLAlchemy models (~822 lines)
│   │   │   ├── enums.py        # All enums (roles, permissions, types)
│   │   │   ├── client.py       # SQLAlchemyClient 
│   │   │   └── config.py       # DatabaseConfig
│   │   ├── caching/            # Cache interface
│   │   ├── vault/              # Vault interface (BaseVault, BaseVaultClient)
│   │   ├── identity/           # Identity interface (ContextIdentityUser)
│   │   ├── middleware/         # Auth middleware (authenticate, check_permissions)
│   │   └── docdatabase/        # Document DB interface
│   ├── caching/                # Redis cache implementation
│   │   ├── client.py           # CacheClient
│   │   ├── dependencies.py     # get_cache_client()
│   │   ├── enums.py            # Cache key enums
│   │   └── redis/              # Redis-specific implementation
│   ├── vault/                  # Vault implementations
│   │   ├── azure_keyvault/     # Azure Key Vault
│   │   ├── hashicorp_vault/    # HashiCorp Vault
│   │   └── dotenv/             # DotEnv vault (development)
│   ├── identity/               # Identity provider implementations
│   │   ├── extra_id/           # Azure AD via MSAL
│   │   └── mock/               # Mock identity for testing
│   ├── docdatabase/            # Document DB implementations
│   ├── exc/                    # Custom exception classes
│   ├── libs/                   # Shared libraries
│   ├── message_broker/         # RabbitMQ/Kafka integration
│   └── utils/                  # Utility functions
├── pyproject.toml              # Project config + pytest config
├── alembic.ini                 # Alembic config
└── docker-compose.yml          # Local infrastructure
```

---

## Core vs Implementation Pattern

**Principle**: `core/` defines WHAT (interfaces), root-level packages define HOW (implementations).

| Interface in `core/` | Implementation | Example |
|-----------------------|---------------|---------|
| `core/vault/vault.py` → `BaseVault` | `vault/hashicorp_vault/` | HashiCorp Vault |
| `core/vault/vault.py` → `BaseVault` | `vault/azure_keyvault/` | Azure Key Vault |
| `core/vault/vault.py` → `BaseVault` | `vault/dotenv/` | DotEnv (dev) |
| `core/caching/` | `caching/redis/` | Redis cache |
| `core/identity/` | `identity/extra_id/` | Azure AD |
| `core/identity/` | `identity/mock/` | Mock (testing) |
| `core/database/client.py` | `core/database/client.py` | SQLAlchemy (single impl) |

---

## Dependencies Pattern

All `Depends()` factories live in `handlers/dependencies/`:

| File | Provides |
|------|----------|
| `database.py` | `get_db_client()` |
| `cache.py` | `get_cache_client()` |
| `vault.py` | `get_vault_client()`, `get_secrets_vault()` |
| `applications.py` | `get_application_handler()` |
| `autonomous_agents.py` | `get_autonomous_agent_handler()` |
| `conversations.py` | `get_conversation_handler()` |
| `credentials.py` | `get_credential_handler()` |
| `custom_groups.py` | `get_custom_group_handler()` |
| `chat_widgets.py` | `get_chat_widget_handler()` |
| `tools.py` | `get_tool_handler()` |
| `resource_permissions.py` | `get_resource_permissions_handler()` |
| `resource_tags.py` | `get_resource_tags_handler()` |
| `tenants.py` | `get_tenant_handler()` |
| `principals.py` | `get_principals_handler()` |
| `tags.py` | `get_tags_handler()` |
| `user_favorites.py` | `get_user_favorites_handler()` |

---

## Adding a New Resource Entity

Follow these steps exactly when adding a new entity (e.g., `DevelopmentPlatform`):

1. **Database model** → `core/database/models.py`: Add `DevelopmentPlatform` + `DevelopmentPlatformMember`
2. **Enum** → `core/database/enums.py`: Add type enum if needed
3. **Migration** → `alembic revision --autogenerate -m "add development_platforms"`
4. **Schemas** → `schema/requests/development_platforms.py` + `schema/responses/development_platforms.py`
5. **Exception** → `exc/development_platforms.py`
6. **Handler** → `handlers/development_platforms.py`
7. **Validator** → `handlers/validators/development_platform_config.py` (if has config)
8. **Dependency** → `handlers/dependencies/development_platforms.py`
9. **Route** → `apis/v1/development_platforms.py`
10. **Register route** → `app.py`: `app.include_router(development_platforms.router, ...)`
11. **Permission config** → `handlers/resource_permissions.py`: Add to `RESOURCE_PERMISSION_CONFIG`
12. **Tag config** → `handlers/resource_tags.py`: Add to `RESOURCE_TAG_CONFIG` (if taggable)
13. **Tests** → `tests/unit/api/v1/`: Create all three files (`test_`, `_rbac`, `_caching`)
14. **Auth enum** → Add `DEVELOPMENT_PLATFORMS_ADMIN` + `DEVELOPMENT_PLATFORMS_CREATOR` to `TenantRolesEnum`
