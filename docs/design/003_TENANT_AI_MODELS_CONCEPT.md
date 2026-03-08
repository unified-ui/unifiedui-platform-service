# Tenant AI Models — Solution Design & Implementation Plan

## 1. Feature Overview

**Ziel:** Tenants können LLM- und Embedding-Modelle registrieren und für verschiedene Zwecke (z.B. Conversation Title Generation, Description Generation, Trace Analysis) nutzen. Mehrere Modelle pro Purpose Group ermöglichen Load-Balancing. Die Integration erfolgt über direkte LLM-API-Calls im Agent-Service (Phase 1), später LangChain als Abstraktionsschicht (Phase 2+).

**Use-Cases für v0.1.0:**
1. **Conversation Title Generation** — Nach der ersten AI-Antwort wird automatisch ein KI-generierter Titel gepatcht
2. **Smart Description Generation** — "Generate with AI" Button auf allen Entities mit Description-Feld
3. **Trace Analysis** — "Analyze Error" bei fehlgeschlagenen Traces + "Summarize with AI" (Short/Medium/Long) bei allen Traces

---

## 2. Design-Entscheidungen & Empfehlungen

### Was ich anders designen würde als dein initialer Entwurf:

#### 2.1 Provider-Enum statt nur Credential-Type
> Du hast `credentials.Type: TENANT_AI_MODEL` vorgeschlagen. Ich empfehle stattdessen einen **eigenen `provider`-Feld** auf `tenant_ai_models`, denn:
> - Credentials sind generisch und mehrere AI Models können dasselbe Credential teilen (z.B. gleicher Azure OpenAI Account, aber verschiedene Deployments/Modelle)
> - Der Credential-Type `TENANT_AI_MODEL` sagt nichts über den konkreten Provider aus
> - Besser: `credentials.type = "AI_MODEL_PROVIDER"` als neuer generischer Type, und `tenant_ai_models.provider` bestimmt den konkreten Provider (AZURE_OPENAI, OPENAI, ANTHROPIC, etc.)

#### 2.2 Config als JSON statt vieler Spalten
> Verschiedene Provider brauchen verschiedene Config-Parameter (Azure braucht endpoint+deployment, OpenAI nur model_name, Anthropic nochmal anders). Daher: **`config: JSON`** Feld mit einem `TenantAIModelConfigValidator` der pro Provider die richtige Config validiert — genau wie bei Chat Agents.

#### 2.3 Purpose Groups flexibler gestalten
> Statt fest auf 2 Purpose Groups zu beschränken, empfehle ich ein JSON-Array-Feld `purpose_groups: list[str]`. Ein Modell kann für mehrere Zwecke taugen.

#### 2.4 Load-Balancing über `priority` + `is_active`
> Statt komplexer Load-Balancing-Logik: Jedes Model bekommt ein `priority: int` Feld. Der Agent-Service wählt Round-Robin aus aktiven Models mit gleicher Priority, oder Fallback auf niedrigere Priority bei Fehler.

#### 2.5 Kein RBAC pro Model — Tenant-Rollen stattdessen
> AI Models sind tenant-weite Konfiguration und brauchen **keine eigene Members-Tabelle**. Stattdessen:
> - `GLOBAL_ADMIN` kann alles managen
> - `TENANT_AI_MODELS_ADMIN` (neue Rolle) kann AI Models auf Tenant-Ebene verwalten
> - Alle Tenant-Mitglieder mit `READER`-Rolle können AI Models sehen (lesen)
> - Das vereinfacht das Modell erheblich — keine `tenant_ai_model_members` Tabelle nötig

#### 2.6 Alle LLM-Calls über Agent-Service
> Description Generation, Trace Analysis, Title Generation — alles läuft über den Agent-Service. Der Platform-Service liefert nur Config, der Agent-Service führt aus. Frontend ruft Agent-Service Endpoints auf.

#### 2.7 "Test Model" Button in der Konfiguration
> Beim Erstellen/Editieren eines AI Models gibt es einen **"Test Model"** Button. Dieser sendet eine einfache Ping-Message an das LLM (z.B. `"Reply with: OK"`) und prüft, ob die Config + Credential funktionieren. Erfolg → grüner Toast. Fehler → Fehlermeldung im Dialog. Der Test läuft über den Agent-Service (`POST /ai/test-model`).

#### 2.8 Tracing-Daten als TOML statt JSON
> Wenn Trace-Objekte an den LLM gesendet werden (für Analyze Error und Summarize), werden sie vorher in **TOML-Format** konvertiert. TOML ist deutlich kompakter als JSON (keine Klammern, weniger Anführungszeichen) und **spart signifikant Tokens** bei großen Trace-Objekten.

#### 2.9 "Analyze Error" als Dialog statt Slide-Over
> Im Gegensatz zum "Summarize with AI" (das ein Slide-Over Panel nutzt) öffnet **"Analyze Error" einen einfachen Dialog (Modal)** mit der AI-Antwort. Das ist angemessener, da Error-Analyse typischerweise einen einzelnen Node betrifft und keine parallele Navigation erfordert.

---

## 3. Unterstützte LangChain Provider & Config

### 3.1 LLM Chat Models (Phase 1 — Top-Priorität)

| Provider | LangChain Package | Config-Felder |
|----------|------------------|---------------|
| **Azure OpenAI** | `langchain-openai` (`AzureChatOpenAI`) | `endpoint`, `api_version`, `deployment_name`, `api_key` (via credential) |
| **OpenAI** | `langchain-openai` (`ChatOpenAI`) | `model_name`, `api_key` (via credential), `organization?`, `base_url?` |
| **Anthropic** | `langchain-anthropic` (`ChatAnthropic`) | `model_name`, `api_key` (via credential) |
| **Google (Gemini)** | `langchain-google-genai` (`ChatGoogleGenerativeAI`) | `model_name`, `api_key` (via credential) |
| **Ollama** (Self-hosted) | `langchain-ollama` (`ChatOllama`) | `model_name`, `base_url` |

### 3.2 LLM Chat Models (Phase 2 — Nice-to-have)

| Provider | LangChain Package | Config-Felder |
|----------|------------------|---------------|
| **Mistral AI** | `langchain-mistralai` | `model_name`, `api_key` |
| **Groq** | `langchain-groq` | `model_name`, `api_key` |
| **AWS Bedrock** | `langchain-aws` | `model_id`, `region`, `credentials_profile` |
| **Deepseek** | `langchain-deepseek` | `model_name`, `api_key` |
| **Cohere** | `langchain-cohere` | `model_name`, `api_key` |

### 3.3 Embedding Models (Phase 1)

| Provider | LangChain Package | Config-Felder |
|----------|------------------|---------------|
| **Azure OpenAI** | `langchain-openai` (`AzureOpenAIEmbeddings`) | `endpoint`, `api_version`, `deployment_name`, `api_key` |
| **OpenAI** | `langchain-openai` (`OpenAIEmbeddings`) | `model_name`, `api_key` |
| **Ollama** | `langchain-ollama` (`OllamaEmbeddings`) | `model_name`, `base_url` |

### 3.4 Credential-Config pro Provider

```
AI_MODEL_PROVIDER Credential secret_value (JSON):
├── AZURE_OPENAI:   { "api_key": "..." }
├── OPENAI:         { "api_key": "..." }
├── ANTHROPIC:      { "api_key": "..." }
├── GOOGLE_GENAI:   { "api_key": "..." }
├── OLLAMA:         {}  (kein API Key nötig, self-hosted)
├── MISTRAL:        { "api_key": "..." }
└── GROQ:           { "api_key": "..." }
```

---

## 4. Entity Design

### 4.1 `tenant_ai_models` (Neue Tabelle)

```
tenant_ai_models
├── id: str (UUID, PK)
├── tenant_id: str (FK → tenants.id, CASCADE)
├── name: str (max 255) — Display-Name, z.B. "GPT-4o Production"
├── description: str (optional, max 2000)
├── type: enum [LLM_MODEL, EMBEDDING_MODEL]
├── provider: enum [AZURE_OPENAI, OPENAI, ANTHROPIC, GOOGLE_GENAI, OLLAMA, MISTRAL, GROQ]
├── purpose_groups: JSON/Array [CONVERSATION_TITLE_GENERATION, DESCRIPTION_GENERATION, ...]
├── config: JSON — Provider-spezifische Config (OHNE Secrets!)
│   ├── Azure OpenAI: { "endpoint": "https://...", "api_version": "2024-12-01-preview", "deployment_name": "gpt-4o" }
│   ├── OpenAI:       { "model_name": "gpt-4o", "organization": "org-...", "base_url": null }
│   ├── Anthropic:    { "model_name": "claude-sonnet-4-20250514" }
│   ├── Ollama:       { "model_name": "llama3", "base_url": "http://localhost:11434" }
│   └── ...
├── credential_id: str (FK → credentials.id, SET NULL, optional) — Referenz auf Credential mit API Key
├── priority: int (default 0) — Für Load-Balancing/Fallback (0 = höchste Priorität)
├── is_active: bool (default false)
└── created_at, updated_at, created_by, updated_by (AuditMixin)
```

> **Kein `tenant_ai_model_members`!** Zugriffssteuerung läuft über Tenant-Rollen:
> - `GLOBAL_ADMIN` / `TENANT_AI_MODELS_ADMIN` → CRUD auf alle AI Models
> - `READER` (alle Tenant-Mitglieder) → Können AI Models sehen

### 4.2 Credential Erweiterung

```
CredentialTypeEnum (erweitert):
├── API_KEY (bestehend)
├── BASIC_AUTH (bestehend)
├── OPENAPI_CONNECTION (bestehend)
└── AI_MODEL_PROVIDER (NEU) — { "api_key": "sk-..." }
```

### 4.3 Neue Enums

```python
class AIModelTypeEnum(str, Enum):
    LLM_MODEL = "LLM_MODEL"
    EMBEDDING_MODEL = "EMBEDDING_MODEL"

class AIModelProviderEnum(str, Enum):
    AZURE_OPENAI = "AZURE_OPENAI"
    OPENAI = "OPENAI"
    ANTHROPIC = "ANTHROPIC"
    GOOGLE_GENAI = "GOOGLE_GENAI"
    OLLAMA = "OLLAMA"
    MISTRAL = "MISTRAL"
    GROQ = "GROQ"

class AIModelPurposeGroupEnum(str, Enum):
    CONVERSATION_TITLE_GENERATION = "CONVERSATION_TITLE_GENERATION"
    CONVERSATION_SUMMARIZATION = "CONVERSATION_SUMMARIZATION"
    DESCRIPTION_GENERATION = "DESCRIPTION_GENERATION"
    TRACE_ANALYSIS = "TRACE_ANALYSIS"
    GENERAL = "GENERAL"
```

### 4.4 Neue Tenant-Rolle

```python
class TenantRolesEnum(str, Enum):
    # ... bestehende Rollen ...
    TENANT_AI_MODELS_ADMIN = "TENANT_AI_MODELS_ADMIN"
```

---

## 5. API Routes

### 5.1 Platform-Service — Tenant AI Models CRUD

Prefix: `/api/v1/platform-service/tenants/{tenant_id}/ai-models`

| Method | Path | Beschreibung | Permissions |
|--------|------|-------------|------------|
| GET | `/ai-models` | Liste AI Models | `authenticate()` — alle Tenant-Mitglieder |
| POST | `/ai-models` | Neues AI Model anlegen | `GLOBAL_ADMIN`, `TENANT_AI_MODELS_ADMIN` |
| GET | `/ai-models/{id}` | AI Model Detail | `authenticate()` — alle Tenant-Mitglieder |
| PATCH | `/ai-models/{id}` | AI Model updaten | `GLOBAL_ADMIN`, `TENANT_AI_MODELS_ADMIN` |
| DELETE | `/ai-models/{id}` | AI Model löschen | `GLOBAL_ADMIN`, `TENANT_AI_MODELS_ADMIN` |

> **Keine `/principals` Endpoints** — Zugriff läuft komplett über Tenant-Rollen.

### 5.2 Platform-Service — AI Models Config Endpoint (Service-to-Service)

| Method | Path | Beschreibung | Auth |
|--------|------|-------------|------|
| GET | `/ai-models/by-purpose?purpose_group=...&type=LLM_MODEL` | Aktive Models nach Purpose | `X-Service-Key` + Bearer |

> Gibt Models inkl. entschlüsselter Credential-Secrets zurück (Service-to-Service only!).

### 5.3 Platform-Service — Conversation PATCH (bestehend, kein Change nötig)

| Method | Path | Beschreibung |
|--------|------|-------------|
| PATCH | `/conversations/{id}` | Name updaten (wird vom Agent-Service aufgerufen) |

### 5.4 Agent-Service — AI Feature Endpoints (NEU)

Prefix: `/api/v1/agent-service/tenants/{tenant_id}/ai`

| Method | Path | Beschreibung | Auth |
|--------|------|-------------|------|
| POST | `/ai/generate-description` | Description generieren/verbessern | Bearer |
| POST | `/ai/analyze-trace` | Trace Fehler analysieren | Bearer |
| POST | `/ai/summarize-trace` | Trace zusammenfassen (Short/Medium/Long) | Bearer |
| GET | `/ai/capabilities` | Verfügbare AI-Features für diesen Tenant | Bearer |
| POST | `/ai/test-model` | Model-Config testen (Ping an LLM) | Bearer |

#### 5.4.1 `POST /ai/generate-description`

```json
// Request
{
  "entity_type": "chat_agent",       // chat_agent | autonomous_agent | tool | credential | chat_widget | ai_model
  "entity_name": "My N8N Agent",
  "existing_description": "n8n bot",  // Optional — roh-description die poliert werden soll
  "context": {                         // Optional — zusätzlicher Kontext
    "type": "N8N",
    "config": { ... }
  }
}

// Response
{
  "description": "An N8N-based conversational AI agent for automated customer support workflows with integrated ticket management."
}
```

#### 5.4.2 `POST /ai/analyze-trace`

```json
// Request
{
  "trace_id": "uuid",
  "node_id": "uuid",                   // Optionaler spezifischer Node
  "error": "Connection refused...",
  "node_name": "HTTP Request",
  "node_type": "http",
  "input": { ... },
  "output": null
}

// Response
{
  "analysis": "## Error Analysis\n\n**Root Cause:** The HTTP endpoint at `https://api.example.com/v2/users` is unreachable...\n\n**Suggested Fix:**\n1. Verify the endpoint URL...\n2. Check network connectivity..."
}
```

#### 5.4.3 `POST /ai/summarize-trace`

```json
// Request
{
  "trace_id": "uuid",
  "detail_level": "short",            // short | medium | long
  "nodes": [                           // Trace-Nodes zur Analyse
    { "name": "Agent", "type": "agent", "status": "completed", "duration": 2.3, ... },
    { "name": "Tool Call", "type": "tool", "status": "completed", ... }
  ]
}

// Response
{
  "summary": "## Trace Summary\n\n**Status:** Completed in 4.2s\n**Flow:** User query → Agent reasoning → Tool call (web search) → Response generation\n\n**Key observations:** ..."
}
```

#### 5.4.4 `POST /ai/test-model`

```json
// Request
{
  "provider": "AZURE_OPENAI",
  "config": {
    "endpoint": "https://my-resource.openai.azure.com/",
    "api_version": "2024-12-01-preview",
    "deployment_name": "gpt-4o"
  },
  "credential_id": "uuid"        // Optional — existing credential
}

// Response (Success)
{ "success": true, "message": "Model responded successfully", "response_time_ms": 423 }

// Response (Failure)
{ "success": false, "message": "Authentication failed: Invalid API key", "response_time_ms": 0 }
```

#### 5.4.5 `GET /ai/capabilities`

```json
// Response — Frontend nutzt dies um AI-Buttons ein/auszublenden
{
  "title_generation": true,            // Hat aktive LLM Models mit CONVERSATION_TITLE_GENERATION
  "description_generation": true,      // Hat aktive LLM Models mit DESCRIPTION_GENERATION
  "trace_analysis": true,              // Hat aktive LLM Models mit TRACE_ANALYSIS
  "summarization": false               // Keine Models für CONVERSATION_SUMMARIZATION
}
```

> **Wichtig:** Das Frontend ruft `GET /ai/capabilities` beim Laden und cached das Ergebnis im Context. AI-Buttons werden **nur** angezeigt wenn die jeweilige Capability `true` ist.

### 5.5 Title Generation — Interner Flow (kein Public Endpoint)

```
User sendet 1. Nachricht
  → Agent-Service erstellt Conversation (via FE)
  → Agent antwortet (Streaming)
  → Nach STREAM_END: Agent-Service prüft ob 1. Nachricht
  → Wenn ja + AI Models konfiguriert:
    → Ruft Platform-Service GET /ai-models/by-purpose?purpose_group=CONVERSATION_TITLE_GENERATION ab
    → Baut LLM Client
    → Generiert Titel
    → PATCHt Conversation-Name via Platform-Service
    → Sendet SSE Event: CONVERSATION_TITLE_UPDATE
```

### 5.6 SSE Event Types (NEU)

```typescript
SSEStreamMessageType.CONVERSATION_TITLE_UPDATE = "CONVERSATION_TITLE_UPDATE"

// Event payload
{
  type: "CONVERSATION_TITLE_UPDATE",
  config: {
    conversationId: "uuid",
    title: "KI-generierter Titel"
  }
}
```

---

## 6. Architektur-Diagramm

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│   Frontend   │────▶│   Agent-Service   │────▶│  Platform-Service    │
│  (React/TS)  │◀────│   (Go/Gin)        │◀────│  (Python/FastAPI)    │
└─────────────┘ SSE  └──────────────────┘ HTTP └─────────────────────┘
      │                       │                         │
      │ POST /ai/*            │ Direct LLM Calls        │ PostgreSQL
      │                       ▼                         ▼
      │              ┌──────────────┐          ┌──────────────────┐
      │              │  LLM Provider │          │  tenant_ai_models │
      │              │  (Azure/OAI/ │          │  credentials      │
      │              │   Anthropic)  │          │  conversations    │
      │              └──────────────┘          └──────────────────┘
      │
      ▼
  ┌────────────────────────────────────────┐
  │  AI Capabilities Context (FE)          │
  │  → Steuert Sichtbarkeit aller         │
  │    AI-Buttons basierend auf            │
  │    GET /ai/capabilities                │
  └────────────────────────────────────────┘
```

### Use-Case Flows:

```
Title Generation (automatisch, nach 1. Antwort):
  FE → POST /messages → Agent-Service → Streaming → STREAM_END
  → async: Agent-Service → GET /ai-models/by-purpose → LLM → PATCH /conversations → SSE Event

Description Generation (User-triggered):
  FE → POST /ai/generate-description → Agent-Service → GET /ai-models/by-purpose → LLM → Response
  FE ← { description: "..." }

Trace Error Analysis (User-triggered):
  FE → POST /ai/analyze-trace → Agent-Service → GET /ai-models/by-purpose → LLM → Response
  FE ← { analysis: "## Error Analysis\n..." }

Trace Summarization (User-triggered):
  FE → POST /ai/summarize-trace → Agent-Service → GET /ai-models/by-purpose → LLM → Response
  FE ← { summary: "## Trace Summary\n..." }
```

---

## 7. Frontend UI Design

### 7.1 Tenant Settings > AI Models

```
┌─────────────────────────────────────────────────────────┐
│  Tenant Settings > AI Models                            │
├─────────────────────────────────────────────────────────┤
│  [+ Add AI Model]    [Search...]    [Filter: Type ▾]    │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │ 🟢 GPT-4o Production        Azure OpenAI | LLM   │  │
│  │    Purpose: Title Gen, Description Gen, General    │  │
│  │    Priority: 0                                     │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │ 🟢 Claude Sonnet             Anthropic | LLM      │  │
│  │    Purpose: Trace Analysis                         │  │
│  │    Priority: 0                                     │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │ 🔴 text-embedding-3-large    OpenAI | Embedding   │  │
│  │    Purpose: General                                │  │
│  │    Priority: 0                                     │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 7.2 AI Model Dialog (Create/Edit)

```
┌─────────────────────────────────────────┐
│  Create AI Model                    [X] │
├─────────────────────────────────────────┤
│                                         │
│  Name:     [________________________]   │
│  Description: [____________________]    │
│                                         │
│  Type:     [LLM Model          ▾]       │
│  Provider: [Azure OpenAI       ▾]       │
│                                         │
│  ── Provider Configuration ──           │
│  Endpoint:        [https://...    ]     │
│  API Version:     [2024-12-01-pre ▾]    │
│  Deployment Name: [gpt-4o         ]     │
│                                         │
│  Credential: [Select Credential  ▾]    │
│              [+ Create new]             │
│                                         │
│  Purpose Groups: [☑ Title Gen]          │
│                  [☐ Summarization]      │
│                  [☑ Description Gen]    │
│                  [☑ Trace Analysis]     │
│                  [☑ General]            │
│                                         │
│  Priority: [0]                          │
│  Active:   [Toggle ON/OFF]              │
│                                         │
│  [🔌 Test Model]                        │
│                                         │
│           [Cancel]  [Create]            │
└─────────────────────────────────────────┘
```

### 7.3 "Generate with AI" Button (Description Generation)

Platzierung: Neben dem Description-Feld in Create/Edit Dialogen aller Entities.

```
  Description: [My raw notes about th]  [✨] ← "Generate with AI" Tooltip
                                          │
                                          ▼ onClick:
                              POST /ai/generate-description
                              {
                                entity_type: "chat_agent",
                                entity_name: "My App",
                                existing_description: "My raw notes about th..."
                              }
                              → Ergebnis wird ins Description-Feld geschrieben
```

**Verhalten:**
- Button ist ein kleines AI-Stern-Icon (✨) mit Tooltip "Generate with AI"
- Nur sichtbar wenn `capabilities.description_generation === true`
- Wenn `existing_description` vorhanden → LLM poliert die Roh-Description auf
- Wenn leer → LLM generiert basierend auf `entity_name` + `context`
- Während Loading: Spinner im Icon, Description-Feld disabled
- Ergebnis wird ins Feld gesetzt, User kann noch editieren vor Speichern

**Betroffene Entities:**
- Chat Agents (Create/Edit Dialog)
- Autonomous Agents (Create/Edit Dialog)
- Tools (Create/Edit Dialog)
- Credentials (Create/Edit Dialog)
- Chat Widgets (Create/Edit Dialog)
- AI Models (Create/Edit Dialog)

### 7.4 Trace Analysis — Slide-Over Panel

#### 7.4.1 Fehlerhafte Traces: "Analyze Error" Button

In der Traces-Liste: Bei Traces/Nodes mit `status: FAILED` wird ein "Analyze Error" Text-Button/Link in der Zeile angezeigt.

```
┌────────────────────────────────────────────────────────────┐
│  Traces                                                     │
├────────────────────────────────────────────────────────────┤
│  ✅ Agent Run          2.3s    completed                    │
│  ✅ Tool: Web Search   0.8s    completed                    │
│  ❌ HTTP Request        —      failed     [Analyze Error]   │
│  ✅ Response Gen        1.1s   completed                    │
└────────────────────────────────────────────────────────────┘
```

Click auf "Analyze Error" → Öffnet einen **Dialog (Modal)** mit der AI-Analyse.

#### 7.4.2 Trace Detail: "Summarize with AI" Split-Button

Wenn man einen Trace öffnet (Trace-Detail-View), gibt es oben rechts einen Split-Button:

```
┌──────────────────────────────────────────────────────────────┐
│  Trace: Agent Run #abc123                                    │
│                                          [✨ Summarize ▾]    │
│                                           ├─ Short (default) │
│                                           ├─ Medium          │
│                                           └─ Long            │
├──────────────────────────────────────────────────────────────┤
│  Nodes: ...                                                  │
└──────────────────────────────────────────────────────────────┘
```

**Split-Button Design:**
- Linker Teil: "✨ Summarize" → Klick = Short (Default)
- Rechter Teil: Dropdown-Pfeil (▾) → Öffnet Menü mit Short / Medium / Long
- Nur sichtbar wenn `capabilities.trace_analysis === true`

#### 7.4.3 Analyze Error Dialog

"Analyze Error" öffnet einen **Dialog (Modal)** mit der AI-Analyse:

```
┌─────────────────────────────────────────────┐
│  AI Error Analysis                      [X] │
├─────────────────────────────────────────────┤
│                                             │
│  ## Error Analysis                          │
│                                             │
│  **Root Cause:**                            │
│  The HTTP endpoint at `api.example.com`     │
│  returned a 503 Service Unavailable...      │
│                                             │
│  **Suggested Fixes:**                       │
│  1. Check if the target service is running  │
│  2. Verify the URL is correct               │
│  3. Check for rate limiting                 │
│                                             │
│  ---                                        │
│  _Generated with GPT-4o_                    │
│                                             │
│  [Re-generate]  [Copy]          [Close]     │
└─────────────────────────────────────────────┘
```

#### 7.4.4 AI Summarize Slide-Over Panel

"Summarize with AI" öffnet ein Slide-Over Panel von rechts:

```
┌────────────────────┬──────────────────────────────────┐
│                    │  AI Analysis                 [X] │
│   Trace Detail     │──────────────────────────────────│
│   (bestehend)      │                                  │
│                    │  ## Error Analysis               │
│                    │                                  │
│                    │  **Root Cause:**                  │
│                    │  The HTTP endpoint at             │
│                    │  `api.example.com` returned       │
│                    │  a 503 Service Unavailable...     │
│                    │                                  │
│                    │  **Suggested Fixes:**             │
│                    │  1. Check if the target service   │
│                    │     is running                    │
│                    │  2. Verify the URL is correct     │
│                    │  3. Check for rate limiting       │
│                    │                                  │
│                    │  ---                              │
│                    │  _Generated with GPT-4o_          │
│                    │                                  │
│                    │  [Re-generate] [Copy]             │
└────────────────────┴──────────────────────────────────┘
```

**Panel Features:**
- Slide-Over von rechts (ähnlich wie Tracing-Sidebar, ~400px breit)
- Markdown-Rendering für die AI-Antwort
- Loading-State: Skeleton/Spinner während LLM generiert
- Footer: "Re-generate" Button + "Copy to Clipboard" Button
- Kleiner Hinweis welches Model verwendet wurde: "_Generated with GPT-4o_"
- Panel bleibt offen, auch wenn man in der Trace-Hierarchie navigiert
- Schließen: X-Button oder Escape

> **Zukunft:** Dieses Panel kann zu einem vollwertigen AI-Chat-Panel erweitert werden, wo man Follow-up-Fragen stellen kann ("Explain step 3 in more detail", "How do I fix the rate limit?").

---

## 8. Schema-Definitionen

### 8.1 Request Schemas (Platform-Service)

```python
class CreateTenantAIModelRequest(BaseModel):
    name: str                                    # max 255
    description: Optional[str] = None            # max 2000
    type: AIModelTypeEnum                        # LLM_MODEL | EMBEDDING_MODEL
    provider: AIModelProviderEnum                # AZURE_OPENAI | OPENAI | ...
    purpose_groups: list[AIModelPurposeGroupEnum] # [CONVERSATION_TITLE_GENERATION, ...]
    config: dict                                 # Provider-specific, validated
    credential_id: Optional[str] = None          # FK to credentials
    priority: int = 0                            # 0 = highest
    is_active: bool = False

class UpdateTenantAIModelRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    purpose_groups: Optional[list[AIModelPurposeGroupEnum]] = None
    config: Optional[dict] = None
    credential_id: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None
```

### 8.2 Response Schemas (Platform-Service)

```python
class TenantAIModelResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: Optional[str]
    type: AIModelTypeEnum
    provider: AIModelProviderEnum
    purpose_groups: list[AIModelPurposeGroupEnum]
    config: dict
    credential_id: Optional[str]
    priority: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]
    updated_by: Optional[str]

class TenantAIModelListResponse(BaseModel):
    items: list[TenantAIModelResponse]
    total: int
```

### 8.3 Service-to-Service Response (mit Secrets)

```python
class AIModelWithSecretResponse(BaseModel):
    """Internal response - includes decrypted credential for agent-service."""
    id: str
    type: AIModelTypeEnum
    provider: AIModelProviderEnum
    config: dict
    credential_secret: Optional[dict]  # Decrypted { "api_key": "..." }
    priority: int
```

---

## 9. Config Validation Examples

### Azure OpenAI (LLM)
```json
{
  "endpoint": "https://my-resource.openai.azure.com/",
  "api_version": "2024-12-01-preview",
  "deployment_name": "gpt-4o"
}
```

### OpenAI (LLM)
```json
{
  "model_name": "gpt-4o",
  "organization": "org-xxx",
  "base_url": null
}
```

### Anthropic (LLM)
```json
{
  "model_name": "claude-sonnet-4-20250514"
}
```

### Google Gemini (LLM)
```json
{
  "model_name": "gemini-2.0-flash"
}
```

### Ollama (LLM, self-hosted)
```json
{
  "model_name": "llama3.1",
  "base_url": "http://localhost:11434"
}
```

---

## 10. Prompts

### 10.1 Title Generation

```
System: You are a conversation title generator. Generate a concise, descriptive title
(maximum 50 characters) for the following conversation. The title should capture the
main topic. Return ONLY the title, nothing else. No quotes, no prefix.

User: {user_first_message}
Assistant: {assistant_first_response_snippet_500_chars}
```

### 10.2 Description Generation (mit bestehender Roh-Description)

```
System: You are a technical writer. Improve the following raw description into a
clear, professional, concise description (1-2 sentences, max 200 characters).
Keep the original intent. Return ONLY the improved description, nothing else.

Entity type: {entity_type}
Entity name: {entity_name}
Raw description: {existing_description}
```

### 10.3 Description Generation (ohne bestehende Description)

```
System: You are a technical writer. Generate a clear, professional, concise description
(1-2 sentences, max 200 characters) for the following entity. Return ONLY the
description, nothing else.

Entity type: {entity_type}
Entity name: {entity_name}
Additional context: {json_context}
```

### 10.4 Trace Error Analysis

```
System: You are a DevOps and AI agent debugging expert. Analyze the following trace
error and provide:
1. Root cause analysis
2. Suggested fixes (actionable steps)
3. Prevention tips

Format your response in Markdown. Be concise but thorough.

Node: {node_name} (type: {node_type})
Status: FAILED
Error: {error_message}
Input (TOML):
{input_toml}
Output (TOML):
{output_toml}
```

### 10.5 Trace Summarization

```
System: You are a trace analysis expert. Summarize the following agent execution trace.
Detail level: {short|medium|long}

For "short": 2-3 sentences covering status, total duration, and main flow.
For "medium": Include each major step, durations, and notable observations.
For "long": Detailed analysis of every node, data flow, performance, and recommendations.

Format in Markdown.

Trace nodes (TOML):
{nodes_toml}
```

---

## 11. Risiken & Offene Punkte

| # | Thema | Risiko/Frage |
|---|-------|-------------|
| 1 | **LLM Libraries in Go** | Go hat kein natives LangChain. Für Phase 1 reichen direkte API-Calls (`go-openai`, Provider-spezifische SDKs), für Phase 2+ braucht es einen Python-Sidecar. |
| 2 | **Secrets im Transit** | Service-to-Service Endpoint gibt entschlüsselte API Keys zurück. TLS-Verschlüsselung + starker Service-Key sicherstellen. |
| 3 | **Rate Limiting** | LLM API Calls kosten Geld. Title-Generation nur 1x pro Conversation. Description Gen: Button muss Debounce haben. |
| 4 | **Latency** | Title-Generation async (fire-and-forget Goroutine). Description/Trace-Analyse synchron, aber mit Loading-State im FE. |
| 5 | **Fallback** | Wenn keine AI Models konfiguriert → Verhalten wie bisher. AI-Buttons unsichtbar. Kein Breaking Change. |
| 6 | **Multi-Tenant Isolation** | AI Model Configs sind tenant-scoped. GET /ai/capabilities prüft nur Models des eigenen Tenants. |
| 7 | **AI-Button Visibility** | FE cached `GET /ai/capabilities` im AICapabilitiesContext. Cache wird invalidiert bei Änderungen in AI Settings. |

---

## 12. Detaillierter Implementierungsplan

### Phase 1: Platform-Service — Entity & CRUD (~2-3 Tage)

| # | Task | Files |
|---|------|-------|
| 1.1 | Neue Enums: `AIModelTypeEnum`, `AIModelProviderEnum`, `AIModelPurposeGroupEnum` | `core/database/enums.py` |
| 1.2 | Neue TenantRole: `TENANT_AI_MODELS_ADMIN` | `core/database/enums.py` |
| 1.3 | `CredentialTypeEnum` erweitern: `AI_MODEL_PROVIDER` | `handlers/validators/credential_validator.py` |
| 1.4 | Credential Validator: Validation für `AI_MODEL_PROVIDER` secret format | `handlers/validators/credential_validator.py` |
| 1.5 | DB Model: `TenantAIModel` (OHNE Members-Tabelle!) | `core/database/models.py` |
| 1.6 | Alembic Migration | `alembic/versions/` |
| 1.7 | Schemas: Request/Response Models | `schema/requests/tenant_ai_models.py`, `schema/responses/tenant_ai_models.py` |
| 1.8 | Exceptions | `exc/tenant_ai_models.py` |
| 1.9 | Config Validator: `TenantAIModelConfigValidator` (pro Provider) | `handlers/validators/tenant_ai_model_validator.py` |
| 1.10 | Handler: `TenantAIModelHandler` (Tenant-Rolle statt Resource-Permission) | `handlers/tenant_ai_models.py` |
| 1.11 | Dependency: `get_tenant_ai_model_handler` | `handlers/dependencies/tenant_ai_models.py` |
| 1.12 | Routes: CRUD (ohne /principals!) | `apis/v1/tenant_ai_models.py` |
| 1.13 | Route Registration in `app.py` | `app.py` |
| 1.14 | Service-to-Service Endpoint: `GET /ai-models/by-purpose` | `apis/v1/tenant_ai_models.py` |
| 1.15 | Tests: CRUD + Tenant-Role checks | `tests/test_tenant_ai_models.py` |

### Phase 2: Agent-Service — AI Feature Endpoints (~3-4 Tage)

| # | Task | Files |
|---|------|-------|
| 2.1 | Platform-Client: `GetAIModelsByPurpose()`, `UpdateConversation()` | `services/platform/client.go` |
| 2.2 | AI Service: LLM Client Factory (Provider-basiert) | `services/ai/llm_client.go` |
| 2.3 | AI Service: Title Generator | `services/ai/title_generator.go` |
| 2.4 | AI Service: Description Generator | `services/ai/description_generator.go` |
| 2.5 | AI Service: Trace Analyzer (mit TOML-Konvertierung) | `services/ai/trace_analyzer.go` |
| 2.6 | AI Handler: `/ai/*` Endpoints + Capabilities + Test Model | `api/handlers/ai.go` |
| 2.7 | Route Registration | `api/routes/routes.go` |
| 2.8 | SSE Event: `CONVERSATION_TITLE_UPDATE` | `api/sse/writer.go` |
| 2.9 | Integration: Title Gen in `SendMessage` Flow | `api/handlers/messages.go` |
| 2.10 | Tests | `tests/unit/` |

### Phase 3: Frontend — AI Settings + AI Features (~3-4 Tage)

| # | Task | Files |
|---|------|-------|
| 3.1 | Types: AI Model Enums, Request/Response Types | `api/types.ts` |
| 3.2 | API Client: AI Model CRUD + AI Feature methods | `api/client.ts` |
| 3.3 | AICapabilitiesContext: Cacht `/ai/capabilities` | `contexts/AICapabilitiesContext.tsx` |
| 3.4 | TenantPermissionEnum: `TENANT_AI_MODELS_ADMIN` hinzufügen | `api/types.ts` |
| 3.5 | Tenant Settings > AI Models Page (Liste + CRUD) | `pages/TenantSettingsPage/AIModelsPage/` |
| 3.6 | AI Model Dialog (Create/Edit, Provider-dynamisch) | `components/dialogs/AIModelDialog/` |
| 3.7 | GenerateWithAIButton Komponente (✨ Icon-Button) | `components/common/GenerateWithAIButton/` |
| 3.8 | GenerateWithAIButton in alle Entity-Dialoge einbauen | Diverse Dialoge |
| 3.9 | Credential Dialog: `AI_MODEL_PROVIDER` Type Support | Credential Dialog |
| 3.10 | SSE Handler: `CONVERSATION_TITLE_UPDATE` Event | `pages/ConversationsPage/ConversationsPage.tsx` |
| 3.11 | Sidebar Titel-Update bei Empfang des Events | `ChatSidebar.tsx`, `GlobalChatSidebar.tsx` |
| 3.12 | TraceAnalysisPanel: Slide-Over Komponente für Summarize | `components/tracing/TraceAnalysisPanel/` |
| 3.13 | AnalyzeErrorDialog: Modal für Error-Analyse | `components/dialogs/AnalyzeErrorDialog/` |
| 3.14 | "Analyze Error" Button in Trace-Liste (bei FAILED) | Tracing-Komponenten |
| 3.15 | "Summarize with AI" Split-Button in Trace-Detail | Tracing-Komponenten |
| 3.16 | "Test Model" Button in AI Model Dialog | `components/dialogs/AIModelDialog/` |
| 3.17 | Markdown-Renderer für AI-Antworten | `components/common/MarkdownRenderer/` (falls nicht vorhanden) |

---

## 13. Zusammenfassung der Änderungen pro Service

### Platform-Service
- **Neue Dateien (~7):** model, migration, schemas (2), handler, dependency, routes, exceptions, validator
- **Geänderte Dateien (~3):** `enums.py`, `models.py`, `credential_validator.py`, `app.py`
- **Tests (~1-2):** `test_tenant_ai_models.py`
- **Kein RBAC / Members** — deutlich weniger Code als Standard-Entity

### Agent-Service
- **Neue Dateien (~6):** `services/ai/llm_client.go`, `services/ai/title_generator.go`, `services/ai/description_generator.go`, `services/ai/trace_analyzer.go`, `api/handlers/ai.go`
- **Geänderte Dateien (~4):** `services/platform/client.go`, `services/platform/types.go`, `api/handlers/messages.go`, `api/sse/writer.go`, `api/routes/routes.go`
- **Tests (~2-3):** AI service tests

### Frontend-Service
- **Neue Dateien (~8):** AI Models Page, AI Model Dialog, GenerateWithAIButton, TraceAnalysisPanel, AICapabilitiesContext, MarkdownRenderer
- **Geänderte Dateien (~6+):** `types.ts`, `client.ts`, `ConversationsPage.tsx`, `ChatSidebar.tsx`, `GlobalChatSidebar.tsx`, diverse Entity-Dialoge

---

## 14. Zeitschätzung

| Phase | Aufwand | Beschreibung |
|-------|---------|-------------|
| Phase 1: Platform CRUD | 2-3 Tage | Entity (ohne RBAC!), Handler, Routes, Tests |
| Phase 2: Agent-Service AI Endpoints | 3-4 Tage | LLM Client, Title Gen, Description Gen, Trace Analysis, SSE |
| Phase 3: Frontend | 3-4 Tage | Settings Page, AI Buttons, Slide-Over Panel, SSE Handler |
| **Gesamt** | **8-11 Tage** | |
