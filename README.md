# unified-ui Platform Service

> **The backbone of your AI management platform** — Centralized authentication, authorization, and core data management for all unified-ui services.

## What is unified-ui?

**unified-ui** transforms the complexity of managing multiple AI systems into a single, cohesive experience. Organizations deploy agents across diverse platforms—Microsoft Foundry, n8n, LangGraph, Copilot, and custom solutions—resulting in fragmented user experiences, inconsistent monitoring, and operational silos.

unified-ui eliminates these challenges by providing **one interface where every agent converges**.

## Role of the Platform Service

The **Platform Service** is the central authority in the unified-ui architecture. It is the **single source of truth** for:

| Responsibility | Description |
|----------------|-------------|
| 🔐 **Authentication** | Validates user identity via Microsoft Entra ID (Azure AD) |
| 🛡️ **Authorization (RBAC)** | Manages tenant memberships, roles, and resource permissions |
| 🗄️ **Core Database** | Stores tenants, applications, credentials, conversations, and agent configurations |
| 👥 **Identity Management** | Resolves users and groups from identity providers |

### Service Architecture

```
┌─────────────┐     ┌─────────────────────────────────────────────┐
│  Frontend   │────▶│          Platform Service (this)            │
└─────────────┘     │  • Authentication & RBAC                    │
                    │  • Tenants, Applications, Credentials       │
                    │  • Conversations, Autonomous Agents         │
                    └──────────────────┬──────────────────────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              ▼                        ▼                        ▼
     ┌────────────────┐    ┌────────────────┐    ┌────────────────┐
     │ Agent Service  │    │ Future Service │    │ Future Service │
     │  (Go/Gin)      │    │                │    │                │
     └────────────────┘    └────────────────┘    └────────────────┘
              │
              │ Calls Platform Service for:
              │ • User/Token validation
              │ • Config & credential retrieval
              │ • Permission checks
              ▼
     ┌────────────────┐
     │ AI Backends    │
     │ N8N, Foundry,  │
     │ LangGraph, ... │
     └────────────────┘
```

**Key Principle**: Only the Platform Service writes to the core database and manages authentication. All other services delegate auth and core data access to this service.

---

## Tech Stack

| Category | Technology |
|----------|------------|
| **Framework** | FastAPI |
| **Language** | Python 3.13+ |
| **Database** | PostgreSQL (SQLAlchemy + Alembic) |
| **Caching** | Redis |
| **Secrets** | Azure Key Vault / HashiCorp Vault |
| **Identity** | Microsoft Entra ID (MSAL) |
| **Document DB** | MongoDB / Azure Cosmos DB |

---

## Getting Started

### Prerequisites

- Python 3.13+
- Docker & Docker Compose
- PostgreSQL
- Redis

### Installation

```bash
# Clone the repository
git clone https://github.com/enricogoerlitz/unified-ui-backend.git
cd unified-ui-backend

# Set up Python environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[test]"

# Start infrastructure
docker-compose up -d

# Run database migrations
alembic upgrade head

# Start the server
uvicorn unifiedui.app:app --reload
```

The API is available at `http://localhost:8000`

### Available Commands

| Command | Description |
|---------|-------------|
| `uvicorn unifiedui.app:app --reload` | Start dev server |
| `alembic upgrade head` | Run migrations |
| `alembic revision --autogenerate -m "msg"` | Create migration |
| `pytest` | Run tests |
| `pytest -n auto` | Run tests in parallel |

---

## API Overview

All resource endpoints are tenant-scoped: `/api/v1/tenants/{tenant_id}/...`

### Core Endpoints

| Resource | Endpoints |
|----------|-----------|
| **Tenants** | CRUD + member management |
| **Applications** | Agent configurations with permissions |
| **Credentials** | Secure credential storage |
| **Conversations** | Chat session management |
| **Autonomous Agents** | Background agent registry |
| **Custom Groups** | Internal permission groups |
| **Development Platforms** | Platform configurations |
| **Chat Widgets** | Custom UI widget definitions |
| **Identity** | User info, groups, provider data |

### Documentation

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

---

## Project Structure

```
unifiedui/
├── app.py                  # FastAPI entry point
├── logger.py               # Centralized logging
├── apis/v1/                # Route definitions (no business logic)
├── handlers/               # Business logic
├── schema/                 # Pydantic schemas
├── core/                   # Interfaces & base classes
│   ├── database/           # DB models & interfaces
│   ├── vault/              # Vault interfaces
│   ├── caching/            # Cache interfaces
│   └── identity/           # Identity provider interfaces
├── caching/                # Redis implementation
├── vault/                  # Key Vault / HashiCorp implementation
├── identity/               # Entra ID implementation
├── docdatabase/            # MongoDB / Cosmos DB client
├── exc/                    # Custom exceptions
└── utils/                  # Utilities
```

---

## Permission Model

### Tenant-Level Roles

| Role | Description |
|------|-------------|
| `READER` | Can access the tenant and have minimal permissions |
| `GLOBAL_ADMIN` | Full access to all tenant resources |
| `APPLICATIONS_ADMIN` | Manage all applications |
| `APPLICATIONS_CREATOR` | Can create new applications |
| `CREDENTIALS_ADMIN` | Manage all credentials |
| `CREDENTIALS_CREATOR` | Can create new credentials |
| `CONVERSATIONS_ADMIN` | Manage all conversations |
| `CONVERSATIONS_CREATOR` | Can create new conversations |
| `AUTONOMOUS_AGENTS_ADMIN` | Manage all autonomous agents |
| `AUTONOMOUS_AGENTS_CREATOR` | Can create new autonomous agents |

### Resource-Level Permissions

| Permission | Description |
|------------|-------------|
| `READ` | View / use resource |
| `WRITE` | Modify resource |
| `ADMIN` | Full control + manage permissions |

**Hierarchy**: `ADMIN` > `WRITE` > `READ`

---

## License

MIT License — see [LICENSE](LICENSE) for details.
