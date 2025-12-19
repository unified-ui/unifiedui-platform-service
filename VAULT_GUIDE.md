# Vault Implementation Guide

## Overview

The vault system provides secure credential storage with support for multiple vault backends:
- **Azure KeyVault** - Cloud-based secrets management
- **HashiCorp Vault** - Self-hosted secrets management with KV v2 engine

## Architecture

```
core/vault/
├── vault.py          # BaseVault interface
└── client.py         # BaseVaultClient with encrypted caching

vault/
├── azure_keyvault/
│   ├── keyvault.py   # Azure KeyVault implementation
│   └── client.py     # Azure KeyVault client wrapper
└── hashicorp_vault/
    ├── vault.py      # HashiCorp Vault implementation
    └── client.py     # HashiCorp Vault client wrapper

handlers/
└── credentials.py    # Credential handler with caching

apis/v1/
└── credentials.py    # REST API endpoints
```

## Configuration

### Environment Variables

```bash
# Choose vault type
VAULT_TYPE=HASHICORP_VAULT  # or AZURE_KEYVAULT

# HashiCorp Vault
VAULT_ADDR=http://localhost:8200
VAULT_TOKEN=your-vault-token

# Azure KeyVault
AZURE_KEYVAULT_VAULT_NAME=my-keyvault

# Secret encryption key for caching (required for encrypted caching)
SECRETS_ENCRYPTION_KEY=your-secret-encryption-key-min-32-chars

# Redis cache (optional, for secret caching)
CACHE_ENABLED=true
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=admin
```

### Generate Encryption Key

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Features

### 1. Multiple Vault Backends

The system supports pluggable vault backends through the `BaseVault` interface:

```python
from aihub.core.vault.vault import BaseVault

class MyVault(BaseVault):
    def store_secret(self, key: str, value: str, metadata: dict = None) -> str:
        # Store secret and return URI
        pass
    
    def get_secret(self, uri: str) -> Optional[str]:
        # Retrieve secret by URI
        pass
```

### 2. Encrypted Secret Caching

Secrets are cached in Redis with Fernet encryption when `SECRETS_ENCRYPTION_KEY` is set:

- **Encryption**: AES-128 via Fernet cipher
- **Key Derivation**: SHA256 hash of `SECRETS_ENCRYPTION_KEY`
- **TTL**: 3600 seconds (1 hour) by default
- **Automatic Invalidation**: On secret update or deletion

### 3. Smart Caching Strategy

The credential handler implements smart caching:

```python
# List credentials - TTL 300s (5 minutes)
cache_key = f"credentials:list:tenant:{tenant_id}:skip:{skip}:limit:{limit}:filter:{filter}"

# Get credential detail - TTL 600s (10 minutes)
cache_key = f"credentials:detail:tenant:{tenant_id}:cred:{credential_id}"

# Secret values - TTL 3600s (1 hour), encrypted
cache_key = f"vault:secret:{uri_hash}"
```

**Cache Invalidation:**
- `CREATE` → Invalidates list cache
- `UPDATE` → Invalidates list + detail cache
- `DELETE` → Invalidates list + detail cache + secret cache

### 4. API Endpoints

All endpoints require authentication via `@authenticate` decorator:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/tenants/{tenant_id}/credentials` | List credentials (paginated) |
| POST | `/api/v1/tenants/{tenant_id}/credentials` | Create credential with secret |
| GET | `/api/v1/tenants/{tenant_id}/credentials/{id}` | Get credential (no secret) |
| PATCH | `/api/v1/tenants/{tenant_id}/credentials/{id}` | Update credential |
| DELETE | `/api/v1/tenants/{tenant_id}/credentials/{id}` | Delete credential |

**Security Note:** Secrets are NEVER returned in API responses. Use `handler.get_credential_secret()` for internal application use only.

### 5. URI Formats

Each vault backend uses a specific URI format:

**Azure KeyVault:**
```
azurekv://vault-name/secret-name/version
```

**HashiCorp Vault:**
```
vault://host:port/mount_point/path
```

## Usage Examples

### Creating a Credential

```python
from aihub.schema.requests.credentials import CreateCredentialRequest

request = CreateCredentialRequest(
    name="API Key",
    description="External API authentication",
    credential_type="API_KEY",
    secret_value="sk-1234567890abcdef",
    metadata={"service": "openai", "environment": "production"}
)

credential = handler.create_credential(
    tenant_id="tenant-123",
    request=request,
    user_id="user-456"
)
# Secret is stored in vault, credential.credential_uri contains the reference
```

### Retrieving a Secret (Internal Use Only)

```python
# Get credential metadata (safe for API responses)
credential = handler.get_credential(
    tenant_id="tenant-123",
    credential_id="cred-789"
)

# Get actual secret value (internal use only, NOT for API responses)
secret_value = handler.get_credential_secret(
    tenant_id="tenant-123",
    credential_id="cred-789"
)
# Secret is fetched from vault and cached encrypted in Redis
```

### Updating a Secret

```python
from aihub.schema.requests.credentials import UpdateCredentialRequest

request = UpdateCredentialRequest(
    secret_value="sk-new-secret-key",  # Optional
    description="Updated description"  # Optional
)

credential = handler.update_credential(
    tenant_id="tenant-123",
    credential_id="cred-789",
    request=request,
    user_id="user-456"
)
# If secret_value provided, vault is updated and cache invalidated
```

## Database Model

The `Credential` model stores metadata only, NOT the secret:

```python
class Credential(Base, IdNameDescriptionMixin, TenantScopedMixin):
    __tablename__ = "credentials"
    
    type: Mapped[str]           # Credential type (API_KEY, PASSWORD, etc.)
    source: Mapped[str]         # Always "vault"
    credential_uri: Mapped[str]  # Vault URI reference (not the secret!)
    
    # Inherited from mixins:
    # id, tenant_id, name, description, created_at, updated_at, created_by, updated_by
```

## Security Best Practices

1. **Never Log Secrets**: Secrets are excluded from all logs
2. **API Responses**: Never include secret values in API responses
3. **Encryption Key**: Keep `SECRETS_ENCRYPTION_KEY` secure and rotate regularly
4. **Access Control**: Implement proper RBAC for credential access
5. **Audit Logging**: Track all credential access and modifications
6. **Vault Token Rotation**: Rotate vault tokens regularly
7. **TLS/SSL**: Always use HTTPS for vault communication in production

## Testing

### Local Development with HashiCorp Vault

```bash
# Start Vault in dev mode
docker-compose up -d vault

# Vault is available at http://localhost:8200
# Token: admin (from docker-compose.yml)

# Configure environment
export VAULT_TYPE=HASHICORP_VAULT
export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=admin
export SECRETS_ENCRYPTION_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
```

### Azure KeyVault Setup

```bash
# Create KeyVault
az keyvault create --name my-keyvault --resource-group my-rg --location eastus

# Grant access
az keyvault set-policy --name my-keyvault --object-id <user-id> --secret-permissions get set delete list

# Configure environment
export VAULT_TYPE=AZURE_KEYVAULT
export AZURE_KEYVAULT_VAULT_NAME=my-keyvault
export SECRETS_ENCRYPTION_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
```

## Dependencies

Install required packages:

```bash
# Azure KeyVault
pip install azure-keyvault-secrets azure-identity

# HashiCorp Vault
pip install hvac

# Encryption
pip install cryptography

# Already included: redis, pydantic, sqlalchemy, fastapi
```

## Troubleshooting

### Secret Not Found
- Check vault URI format matches backend
- Verify vault connection and credentials
- Check vault access permissions

### Cache Issues
- Verify Redis connection
- Check `SECRETS_ENCRYPTION_KEY` is set
- Inspect cache keys with Redis CLI: `KEYS vault:secret:*`

### Vault Connection Errors
- Test vault connectivity: `curl $VAULT_ADDR/v1/sys/health`
- Verify token/credentials are valid
- Check network/firewall rules

## Migration

To switch vault backends:

1. Export secrets from old vault
2. Update `VAULT_TYPE` configuration
3. Re-create credentials (secrets will be stored in new vault)
4. Update `credential_uri` fields in database if needed

**Note**: No automated migration tool is provided. Plan carefully for production migrations.
