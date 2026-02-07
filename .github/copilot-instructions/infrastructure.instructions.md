# Infrastructure

## Overview

All infrastructure uses the **Core vs Implementation** pattern:
- Interfaces defined in `unifiedui/core/`
- Concrete implementations in sibling packages at root level

---

## Caching (Redis)

### Architecture
```
core/caching/           → Cache interface
caching/
├── client.py           → CacheClient (application-level)
├── dependencies.py     → get_cache_client() singleton
├── enums.py            → Cache key prefix enums
└── redis/
    ├── client.py       → RedisCacheClient
    └── cache.py        → RedisCache (low-level Redis ops)
```

### Cache Client Stack
```
CacheClient
  └── RedisCacheClient
        └── RedisCache (get, set, delete, delete_pattern, ping)
```

### Cache Key Patterns
```
{resource}:list:tenant:{tenant_id}:user:{user_id}:skip:{skip}:limit:{limit}:view:{view}:order:{order}:active:{active}
{resource}:detail:tenant:{tenant_id}:{resource_id}
user:{user_id}:tenants
user:{user_id}:groups
user:{user_id}:custom_groups
```

### Cache Invalidation Rules
| Event | Invalidated Keys |
|-------|-----------------|
| Create/update/delete resource | `{resource}:*:tenant:{tenant_id}:*` |
| Grant permission to user | `{resource}:*:user:{user_id}:*` |
| Grant permission to group | All group member caches |
| Tenant membership change | `user:{user_id}:tenants` |

### X-Use-Cache Header
- `true` (default): Use Redis cache for ContextIdentityUser properties
- `false`: Bypass cache, query DB directly
- Tests ALWAYS use `false` except `test_*_caching.py` files

---

## Vault

### Architecture
```
core/vault/
├── vault.py            → BaseVault (interface)
├── client.py           → BaseVaultClient (interface)
└── config.py           → VaultConfig

vault/
├── azure_keyvault/     → Azure Key Vault implementation
├── hashicorp_vault/    → HashiCorp Vault implementation
└── dotenv/             → DotEnv vault (development only)
```

### Vault Interface
```python
class BaseVault:
    """Base vault interface for secret management."""
    
    def ping(self) -> bool: ...
    def get_secret(self, key: str, use_cache: bool = True) -> str: ...
    def store_secret(self, key: str, value: str) -> str: ...
    def update_secret(self, key: str, value: str) -> str: ...
    def delete_secret(self, key: str) -> None: ...
    def list_secrets(self) -> list[str]: ...
```

### Usage
- **Credentials**: Secret values stored in vault, metadata in PostgreSQL
- **API Keys**: Autonomous agent primary/secondary keys stored in vault
- **Never cache API keys**: `use_cache=False` for API key validation (rotation support)
- **Development**: DotEnv vault uses file-based storage (`.env`)

### Test Mock
Tests use `MockVault` from `tests/fixtures/vault.py` — in-memory dict storage.

---

## Identity Provider

### Architecture
```
core/identity/
├── users.py            → ContextIdentityUser, IdentityUser interfaces
├── groups.py           → Group response models
└── ...

identity/
├── extra_id/           → Azure AD via MSAL (production)
│   └── ...
└── mock/               → Mock identity (testing)
    └── ...
```

### ContextIdentityUser
Created by `@authenticate()` middleware. Properties are lazy-loaded and cached:
- `.identity` → `IdentityUser` with `get_id()`, `get_name()`, `get_email()`
- `.tenants` → List of tenant memberships with roles
- `.groups` → Identity provider groups
- `.custom_groups` → UnifiedUI custom groups

### Test Mock
Tests use `MockIdentityToken` from `tests/fixtures/auth.py`:
```python
user_token = test_client.create_test_user("user-id", "Display Name")
headers = create_auth_headers(user_token, use_cache=False)
```

---

## Document Database

### Architecture
```
core/docdatabase/       → DocDB interface
docdatabase/            → Implementations (MongoDB, CosmosDB)
```

- Used for high-volume, ID-based access data (messages, traces)
- Not used for queryable/filterable data (that goes in PostgreSQL)

---

## Configuration

`unifiedui/core/config.py` uses **pydantic-settings**:

```python
class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str
    
    # Cache
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0
    
    # Vault
    vault_type: str = "dotenv"  # dotenv | hashicorp | azure
    vault_url: Optional[str] = None
    
    # Identity
    azure_tenant_id: str
    azure_client_id: str
    
    # CORS
    cors_origins: list[str] = ["*"]
    
    # Service Keys
    x_agent_service_key: str = ""
    
    model_config = SettingsConfigDict(env_file=".env")
```

Access via: `from unifiedui.core.config import settings`
