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
├── client.py           → BaseVaultClient (encrypted caching, URI building)
└── config.py           → VaultConfig

vault/
├── azure_keyvault/     → Azure Key Vault implementation
├── hashicorp_vault/    → HashiCorp Vault implementation
└── dotenv/             → DotEnv vault (development only)

handlers/dependencies/vault.py → get_app_service_vault(), get_secrets_vault()
```

### Dual Vault Architecture

The system uses **two separate vault instances**, each with their own credentials:

| Vault | Factory | Type Config | Credentials Config | Purpose |
|-------|---------|-------------|--------------------|---------|
| **App Vault** | `get_app_service_vault()` | `APP_VAULT_TYPE` (fallback: `VAULT_TYPE`) | `APP_HASHICORP_VAULT_ADDR`, `APP_HASHICORP_VAULT_TOKEN`, `APP_AZURE_KEYVAULT_URL` | Service-to-service keys |
| **Secrets Vault** | `get_secrets_vault()` | `SECRETS_VAULT_TYPE` (fallback: `VAULT_TYPE`) | `SECRETS_HASHICORP_VAULT_ADDR`, `SECRETS_HASHICORP_VAULT_TOKEN`, `SECRETS_AZURE_KEYVAULT_URL` | Credential secrets (API keys, tokens) |

Both can point to the same vault instance or to completely different backends/addresses.

The factory `_create_vault_client()` takes per-purpose credentials as arguments — it does NOT read global settings.

### Vault Interface
```python
class BaseVault(ABC):
    def store_secret(self, key, value, metadata=None) -> str: ...
    def get_secret(self, uri) -> Optional[str]: ...
    def update_secret(self, uri, value, metadata=None) -> bool: ...
    def delete_secret(self, uri) -> bool: ...
    def build_secret_uri(self, key_name: str) -> str: ...  # URI construction
    def ping(self) -> bool: ...
    def close(self) -> None: ...
    def list_secrets(self) -> list: ...
```

### URI Scheme per Vault Type
| Vault | URI Format | Example |
|-------|-----------|--------|
| DotEnv | `dotenv://{key}` | `dotenv://PLATFORM_TO_AGENT_SERVICE_KEY` |
| HashiCorp | `vault://{host}/{mount}/{key}` | `vault://127.0.0.1:8200/secret/my-key` |
| Azure KV | `azurekv://{vault_name}/{secret}` | `azurekv://uui-vault/my-key` |

**Never hardcode URI prefixes.** Always use `vault.build_secret_uri(key_name)` to construct URIs.

### Vault Caching (BaseVaultClient)
- `get_secret(uri, use_cache=True)` → AES-encrypted Redis cache, 1h TTL
- Requires `SECRETS_ENCRYPTION_KEY` env var for encryption
- `update_secret()` / `delete_secret()` auto-invalidate cache
- **Service keys always use `use_cache=False`** (key rotation must be immediate)

### Service-to-Service Keys
| Key Name | Direction |
|----------|----------|
| `PLATFORM_TO_AGENT_SERVICE_KEY` | Platform → Agent Service |
| `AGENT_TO_PLATFORM_SERVICE_KEY` | Agent → Platform Service |

Used in `auth.py` middleware and `AgentServiceClient`. Both resolve via `app_vault.build_secret_uri(key_name)`.

### Usage
- **Credentials**: Secret values stored in secrets vault, metadata in PostgreSQL
- **API Keys**: Autonomous agent keys stored in secrets vault
- **Service keys**: Stored in app vault, validated with `use_cache=False`
- **Development**: DotEnv vault reads from environment variables via `os.getenv()`

### Test Mock
Tests use `MockVault` from `tests/fixtures/vault.py` — in-memory dict storage with `mock://` URI scheme.

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
    
    # Vault (dual vault support)
    vault_type: str = "dotenv"  # DOTENV | HASHICORP_VAULT | AZURE_KEYVAULT
    app_vault_type: Optional[str] = None     # Override for app vault (fallback: vault_type)
    secrets_vault_type: Optional[str] = None # Override for secrets vault (fallback: vault_type)
    
    # App Vault Credentials
    app_hashicorp_vault_addr: Optional[str] = None
    app_hashicorp_vault_token: Optional[str] = None
    app_azure_keyvault_url: Optional[str] = None
    
    # Secrets Vault Credentials
    secrets_hashicorp_vault_addr: Optional[str] = None
    secrets_hashicorp_vault_token: Optional[str] = None
    secrets_azure_keyvault_url: Optional[str] = None
    
    # Identity
    azure_tenant_id: str
    azure_client_id: str
    
    # CORS
    cors_origins: list[str] = ["*"]
    
    # Agent Service Connection
    agent_service_url: str = "http://localhost:8085"
    agent_service_timeout: int = 30
    
    model_config = SettingsConfigDict(env_file=".env")
```

Access via: `from unifiedui.core.config import settings`
