# Concept: Cascade Delete, CORS & Dual-Vault

## 1. Dual-Vault Konzept

### Motivation

Aktuell wird `X-Service-Key` im Platform Service über `settings.x_agent_service_key` (env var) gelesen.
Service-Secrets sollten im Vault liegen, nicht in Klartext-Env-Variablen.

### Zwei Vault-Instanzen

| Vault | Zweck | Cache | Beispiel-Secrets |
|-------|-------|-------|------------------|
| **App Vault** | Infrastruktur- & Service-Keys | Nein (Keys ändern sich selten, kein Redis nötig) | `X-Service-Key`, `X-Agent-Service-Key` |
| **Secrets Vault** | User-/Business-Secrets | Ja (Fernet-verschlüsselt in Redis) | Credential URIs, Autonomous Agent API Keys |

### Vault-Key-Konvention

```
App Vault Keys (für Service-to-Service Auth):
├── platform-to-agent-service-key    → Key den Platform Service beim Aufruf des Agent Service mitsendet
└── agent-to-platform-service-key    → Key den Agent Service beim Aufruf des Platform Service mitsendet
```

### Configuration (Env Vars)

#### Platform Service

```env
# Vault Backend (shared für beide Vault-Instanzen)
VAULT_TYPE=DOTENV                          # DOTENV | AZURE_KEYVAULT | HASHICORP_VAULT

# Azure Key Vault (wenn VAULT_TYPE=AZURE_KEYVAULT)
AZURE_KEYVAULT_VAULT_NAME=mykeyvault       # für Secrets Vault
APP_AZURE_KEYVAULT_VAULT_NAME=myappkv      # für App Vault (kann gleicher KV sein)

# HashiCorp Vault (wenn VAULT_TYPE=HASHICORP_VAULT)
VAULT_ADDR=http://vault:8200
VAULT_TOKEN=...

# App Vault Keys (logische Key-Namen im Vault)
APP_VAULT_AGENT_SERVICE_KEY=agent-to-platform-service-key
APP_VAULT_PLATFORM_TO_AGENT_KEY=platform-to-agent-service-key

# Agent Service URL (für Cascade Delete Calls)
AGENT_SERVICE_URL=http://localhost:8085
```

#### Agent Service

```env
# Vault Backend
VAULT_TYPE=dotenv

# App Vault Keys (logische Key-Namen im Vault)
APP_VAULT_PLATFORM_SERVICE_KEY=platform-to-agent-service-key
APP_VAULT_AGENT_TO_PLATFORM_KEY=agent-to-platform-service-key
```

### Architektur

```
┌─────────────────────────────────────────────────────────────┐
│                        App Vault                            │
│  (DotEnv / Azure Key Vault / HashiCorp Vault)               │
│                                                             │
│  ┌─────────────────────────────┐  ┌──────────────────────┐  │
│  │ agent-to-platform-svc-key   │  │ platform-to-agent-   │  │
│  │ = "abc123..."               │  │ svc-key = "xyz789.." │  │
│  └─────────────────────────────┘  └──────────────────────┘  │
└──────────────┬──────────────────────────────┬────────────────┘
               │                              │
    ┌──────────▼──────────┐       ┌───────────▼───────────┐
    │  Platform Service   │       │   Agent Service       │
    │                     │       │                       │
    │  Liest:             │       │  Liest:               │
    │  - agent-to-plat.   │       │  - platform-to-agent  │
    │    (für Validierung)│       │    (für Validierung)   │
    │  - platform-to-ag.  │       │  - agent-to-plat.     │
    │    (für Requests)   │       │    (für Requests)     │
    └─────────────────────┘       └───────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      Secrets Vault                          │
│  (DotEnv / Azure Key Vault / HashiCorp Vault)               │
│                                                             │
│  Credential URIs, Autonomous Agent API Keys, etc.           │
│  → Encrypted Cache in Redis (Fernet/AES-256)                │
└─────────────────────────────────────────────────────────────┘
```

### Service-to-Service Auth Flow

```
Platform Service  ──────────────────────────►  Agent Service
                   X-Service-Key: {platform-to-agent-svc-key}
                   (Key aus App Vault geholt)

                   Agent Service validiert:
                   App Vault.get("platform-to-agent-svc-key")
                   == Request Header X-Service-Key?


Agent Service    ──────────────────────────►  Platform Service
                   X-Service-Key: {agent-to-platform-svc-key}
                   (Key aus App Vault geholt)

                   Platform Service validiert:
                   App Vault.get("agent-to-platform-svc-key")
                   == Request Header X-Service-Key?
```

---

## 2. Cascade Delete Konzept

### Flow: DELETE Conversation

```
Frontend
  │  DELETE /tenants/{tenantId}/conversations/{conversationId}
  │  Authorization: Bearer {user-token}
  ▼
Platform Service
  │  1. Auth-Middleware: Bearer Token validieren
  │  2. Permission Check: User hat ADMIN/WRITE auf Conversation
  │  3. Agent Service Client aufrufen:
  │     DELETE /tenants/{tenantId}/conversations/{conversationId}/data
  │     Header: X-Service-Key = app_vault.get("platform-to-agent-svc-key")
  │  4. Bei Fehler: Loggen, aber Conversation trotzdem löschen (best-effort)
  │  5. Conversation aus PostgreSQL löschen (CASCADE → members, tags, favorites)
  │  6. Cache invalidieren
  ▼
Agent Service
  │  1. Middleware: X-Service-Key validieren gegen app_vault
  │  2. docDB.Messages().Delete(ctx, {ConversationID: convId, TenantID: tenantId})
  │  3. docDB.Traces().DeleteByConversation(ctx, tenantId, conversationId)
  │  4. Return 204 No Content
  ▼
MongoDB: Messages + Traces gelöscht
```

### Flow: DELETE Autonomous Agent

```
Frontend
  │  DELETE /tenants/{tenantId}/autonomous-agents/{agentId}
  │  Authorization: Bearer {user-token}
  ▼
Platform Service
  │  1. Auth-Middleware: Bearer Token validieren
  │  2. Permission Check: User hat ADMIN auf Autonomous Agent
  │  3. Agent Service Client aufrufen:
  │     DELETE /tenants/{tenantId}/autonomous-agents/{agentId}/data
  │     Header: X-Service-Key = app_vault.get("platform-to-agent-svc-key")
  │  4. Bei Fehler: Loggen, aber Agent trotzdem löschen (best-effort)
  │  5. Vault Secrets löschen (primary_key_vault_uri, secondary_key_vault_uri)
  │  6. Agent aus PostgreSQL löschen (CASCADE → members, tags, favorites)
  │  7. Cache invalidieren
  ▼
Agent Service
  │  1. Middleware: X-Service-Key validieren gegen app_vault
  │  2. docDB.Traces().DeleteByAutonomousAgent(ctx, tenantId, agentId)
  │  3. Return 204 No Content
  ▼
MongoDB: Traces gelöscht
```

---

## 3. Implementierungsplan

### Phase 1: Dual-Vault (Platform Service)

#### 1.1 Config erweitern — `unifiedui/core/config.py`

```python
# App Vault (separate Konfiguration, kann gleicher Backend-Typ sein)
app_vault_type: Optional[str] = None               # Default: gleicher Typ wie vault_type
app_azure_keyvault_vault_name: Optional[str] = None # Separater KV für App Vault

# App Vault Key Names
app_vault_agent_service_key: str = "agent-to-platform-service-key"
app_vault_platform_to_agent_key: str = "platform-to-agent-service-key"

# Agent Service
agent_service_url: str = "http://localhost:8085"
```

#### 1.2 Vault Dependencies anpassen — `unifiedui/handlers/dependencies/vault.py`

- `get_app_service_vault()` → nutzt `app_vault_type` (Fallback auf `vault_type`)
- `get_secrets_vault()` → bleibt wie bisher (mit Cache)

#### 1.3 Auth-Middleware umstellen — `unifiedui/core/middleware/apis/v1/auth.py`

`_validate_service_key()` ändern:

```python
# ALT:
expected_key = getattr(settings, required_service_auth_key.lower(), None)

# NEU:
app_vault = get_app_service_vault()
vault_key_name = getattr(settings, f"app_vault_{required_service_auth_key.lower()}", None)
expected_key = app_vault.get_secret(f"dotenv://{vault_key_name}", use_cache=False)
```

#### 1.4 Agent Service Client — `unifiedui/utils/agent_service_client.py` (neu)

```python
class AgentServiceClient:
    def __init__(self, base_url: str, app_vault: BaseVaultClient):
        ...

    def _get_service_key(self) -> str:
        key_name = settings.app_vault_platform_to_agent_key
        return self.app_vault.get_secret(f"dotenv://{key_name}", use_cache=False)

    def delete_conversation_data(self, tenant_id: str, conversation_id: str) -> bool:
        ...

    def delete_autonomous_agent_data(self, tenant_id: str, agent_id: str) -> bool:
        ...
```

### Phase 2: Service-Key-Auth (Agent Service)

#### 2.1 Config erweitern — `internal/config/config.go`

```go
type AppVaultConfig struct {
    PlatformServiceKey string  // APP_VAULT_PLATFORM_SERVICE_KEY (key name in vault)
    AgentToPlatformKey string  // APP_VAULT_AGENT_TO_PLATFORM_KEY (key name in vault)
}
```

#### 2.2 Service-Key-Middleware — `internal/api/middleware/service_auth.go` (neu)

```go
func AuthenticateServiceKey(vaultClient vault.Client) gin.HandlerFunc {
    return func(c *gin.Context) {
        serviceKey := c.GetHeader("X-Service-Key")
        expectedKey, _ := vaultClient.GetSecret(ctx, "dotenv://"+cfg.PlatformServiceKey, false)
        if serviceKey != expectedKey {
            c.AbortWithStatusJSON(403, ...)
            return
        }
        c.Next()
    }
}
```

#### 2.3 Neue Bulk-Delete-Endpoints

| Method | Endpoint | Auth | Handler |
|--------|----------|------|---------|
| `DELETE` | `/tenants/{tenantId}/conversations/{conversationId}/data` | X-Service-Key | `DeleteConversationData` |
| `DELETE` | `/tenants/{tenantId}/autonomous-agents/{agentId}/data` | X-Service-Key | `DeleteAutonomousAgentData` |

#### 2.4 Routes erweitern — `internal/api/routes/routes.go`

```go
serviceAuth := v1.Group("/tenants/:tenantId")
serviceAuth.Use(middleware.AuthenticateServiceKey(vaultClient))
{
    serviceAuth.DELETE("/conversations/:conversationId/data", tracesHandler.DeleteConversationData)
    serviceAuth.DELETE("/autonomous-agents/:agentId/data", tracesHandler.DeleteAutonomousAgentData)
}
```

#### 2.5 Platform Client erweitern

`platform.Client` umstellen: Service Key aus App Vault lesen statt aus `config.PlatformConfig.ServiceKey`.

### Phase 3: Cascade Delete (Platform Service)

#### 3.1 Handlers erweitern

- `conversations.py` → `delete_conversation()`: Agent Service Client aufrufen (best-effort)
- `autonomous_agents.py` → `delete_autonomous_agent()`: Agent Service Client aufrufen + Vault Secrets löschen (best-effort)

#### 3.2 Dependencies

- `AgentServiceClient` als Dependency in betroffene Handler injizieren

### Phase 4: CORS (Platform Service)

#### 4.1 Config — `unifiedui/core/config.py`

Default `cors_allow_headers` explizit setzen:

```python
cors_allow_headers: list[str] = [
    "Authorization",
    "Content-Type",
    "Accept",
    "X-Service-Key",
    "X-Request-ID",
    "X-Correlation-ID",
    "X-Unified-UI-Autonomous-Agent-API-Key",
    "Cache-Control",
]
```

### Phase 5: Swagger (Agent Service)

- Swagger-Annotationen für neue Endpoints
- `swag init` regenerieren

### Phase 6: Tests

#### Platform Service
- Unit Tests für `AgentServiceClient` (mit Mock)
- Integration Tests für Cascade Delete
- Tests für App Vault Key-Auflösung in Auth-Middleware

#### Agent Service
- Unit Tests für `AuthenticateServiceKey` Middleware
- Unit Tests für `DeleteConversationData` / `DeleteAutonomousAgentData` Handler

---

## 4. Error Handling

### Best-Effort Cascade Delete

Wenn der Agent Service beim Cascade Delete nicht erreichbar ist:

1. **Loggen** als ERROR mit Kontext (tenant_id, resource_id)
2. **Conversation/Agent trotzdem aus PostgreSQL löschen**
3. Orphaned Data in MongoDB wird toleriert

Begründung: Der Platform Service ist die Source-of-Truth für Entitäten. Traces/Messages sind abgeleitete Daten — es ist besser, die Entität zu löschen als den User zu blockieren.

---

## 5. Setup: Vault Keys manuell anlegen

### Für lokale Entwicklung (DotEnv)

Die folgenden Env-Variablen müssen in `.env` beider Services gesetzt werden:

```env
# .env (Platform Service)
AGENT_TO_PLATFORM_SERVICE_KEY=<generierter-key-1>
PLATFORM_TO_AGENT_SERVICE_KEY=<generierter-key-2>

# .env (Agent Service)
AGENT_TO_PLATFORM_SERVICE_KEY=<gleicher-key-1>
PLATFORM_TO_AGENT_SERVICE_KEY=<gleicher-key-2>
```

Keys generieren (einmalig):

```sh
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Für Azure Key Vault

Zwei Secrets im gemeinsamen (oder separaten) Key Vault anlegen:

```sh
az keyvault secret set --vault-name <vault-name> --name "agent-to-platform-service-key" --value "<key-1>"
az keyvault secret set --vault-name <vault-name> --name "platform-to-agent-service-key" --value "<key-2>"
```

### Für HashiCorp Vault

```sh
vault kv put secret/agent-to-platform-service-key value="<key-1>"
vault kv put secret/platform-to-agent-service-key value="<key-2>"
```

> **TODO**: Diese Setup-Schritte später in die README.md der jeweiligen Services und in TODO.md unter `## CMDs` dokumentieren.
