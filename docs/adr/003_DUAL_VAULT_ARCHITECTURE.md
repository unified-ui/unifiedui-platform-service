# ADR 003: Dual Vault Architecture

## Status

**Accepted** — 2025-12-07

## Context

unified-ui stores sensitive credentials (API keys, secrets, tokens) for AI agent configurations. These credentials must be:

- Encrypted at rest
- Access-controlled
- Auditable
- Deployable across different environments (cloud, on-premises, local dev)

Different deployment scenarios require different secret management solutions:

- **Enterprise/Cloud**: Azure Key Vault or HashiCorp Vault
- **Local Development**: `.env` file or simple key-value store
- **Self-hosted**: HashiCorp Vault (open-source)

## Decision

We implement a **Vault Abstraction Layer** using the factory pattern:

### Architecture

```
core/vault/
├── client.py    # ABC: BaseVaultClient interface
└── vault.py     # ABC: BaseVault interface

vault/
├── azure_keyvault/    # Azure Key Vault implementation
│   ├── client.py      # AzureKeyVaultClient(BaseVaultClient)
│   └── keyvault.py    # AzureKeyVault(BaseVault)
├── hashicorp_vault/   # HashiCorp Vault implementation
│   ├── client.py      # HashiCorpVaultClient(BaseVaultClient)
│   └── vault.py       # HashiCorpVault(BaseVault)
└── dotenv/            # dotenv fallback for local development
    ├── client.py      # DotenvVaultClient(BaseVaultClient)
    └── vault.py       # DotenvVault(BaseVault)
```

### Key Interfaces

- **`BaseVaultClient`** — Low-level operations: `get_secret()`, `set_secret()`, `delete_secret()`, `list_secrets()`
- **`BaseVault`** — High-level operations: `store_credential()`, `get_credential()`, `delete_credential()` with structured metadata

### Selection

The vault implementation is selected at startup based on `Settings.VAULT_PROVIDER`:

| Value | Implementation |
|-------|---------------|
| `azure` | Azure Key Vault (via `azure-keyvault` SDK) |
| `hashicorp` | HashiCorp Vault (via `hvac` library) |
| `dotenv` | Local `.env` file (development only) |

## Consequences

### Positive

- Zero code changes needed when switching vault providers
- Local development works without cloud dependencies
- Production deployments can use enterprise-grade vaults
- Clear separation between low-level client and high-level vault operations

### Negative

- Three implementations to maintain
- Feature parity challenges (Azure Key Vault has features HashiCorp doesn't, and vice versa)
- dotenv vault is inherently insecure — must be restricted to development

## Alternatives Considered

1. **Database-encrypted secrets** — Violates separation of concerns, harder to audit
2. **Single vault (HashiCorp only)** — Adds infrastructure requirement for all deployments
3. **Cloud-native only (Azure Key Vault)** — Blocks self-hosted and multi-cloud use cases
