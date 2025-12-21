# AIHub

[![CI](https://github.com/enricogoerlitz/aihub-backend/actions/workflows/ci.yml/badge.svg)](https://github.com/enricogoerlitz/aihub-backend/actions/workflows/ci.yml)

> **Unified-UI for your AI** — One interface for all your AI agents, regardless of origin.

## Overview

**AIHub** is a unified integration platform that transforms the complexity of managing multiple AI systems into a single, cohesive experience. Organizations today deploy agents across diverse platforms—Microsoft Foundry, n8n, LangGraph, Copilot, and custom solutions—resulting in fragmented user experiences, inconsistent monitoring, and operational silos. AIHub eliminates these challenges by providing a unified interface where every agent converges into one platform.

### Key Features

- 🎯 **Unified Chat Interface** — Single, consistent chat experience for all AI agents
- 🔌 **Multi-Platform Integration** — Microsoft Foundry, n8n, LangGraph, Copilot, and custom agents
- 🎨 **Flexible Widget System** — Custom UI components embedded into conversations
- 📊 **Centralized Tracing** — Unified observability across all agents
- 🔐 **Enterprise Authentication** — Microsoft Entra ID, Google OAuth, and more
- 🌍 **Cloud-Agnostic** — Deploy on Azure, AWS, GCP, or on-premises
- 🚀 **Autonomous Agent Support** — Background agents with centralized tracing

## The Problem AIHub Solves

### Fragmented AI Experiences
- **Inconsistent interfaces**: Each platform has its own chat experience
- **Missing UI layers**: Custom agents (e.g., LangGraph) often lack user interfaces
- **Scattered monitoring**: Tracing data lives in disparate systems

### Integration Complexity
- Custom API integrations for each agent system
- Bespoke authentication and authorization flows
- Redundant implementations of common features

### Rapid Technology Obsolescence
- Agent frameworks evolve quickly; today's tools may be tomorrow's legacy
- **AIHub decouples agent frameworks from user experience**
- Integrate legacy and modern systems simultaneously
- Seamless transitions without disrupting end users

## Architecture

### Technology Stack

- **Backend**: FastAPI (Python) with async request handling
- **Frontend**: React + TypeScript
- **Database**: JSON-based document database (Azure Cosmos DB, MongoDB, or equivalent)
- **Caching**: Redis for permission resolution and frequently accessed data
- **Message Broker**: Azure Event Hubs, AWS Kinesis, GCP Pub/Sub, Kafka, or RabbitMQ
- **Secrets Management**: Azure Key Vault, AWS Secrets Manager, GCP Secret Manager, or HashiCorp Vault
- **Identity**: Multi-provider OAuth 2.0/OIDC (Microsoft Entra ID, Google OAuth, etc.)

### Project Structure

```
aihub/
├── app.py              # FastAPI application entry point
├── logger.py           # Centralized logging
├── apis/v1/            # API route definitions
├── handlers/           # Business logic handlers
├── schema/             # Pydantic schemas
├── core/               # Core interfaces and base implementations
│   ├── database/       # Database models, interfaces
│   ├── vault/          # Vault interfaces
│   ├── caching/        # Caching interfaces
│   └── identity/       # Identity provider interfaces
├── database/           # Database implementations (PostgreSQL, etc.)
├── caching/            # Caching implementations (Redis, etc.)
├── vault/              # Vault implementations
├── identity/           # Identity provider implementations
├── docdatabase/        # Document database client
├── message_broker/     # Message broker integration
├── exc/                # Custom exceptions
├── libs/               # Shared libraries
└── utils/              # Utility functions
```

### Core Design Patterns

**Factory Pattern**: Extensive use for agent systems, infrastructure components (databases, caches, vaults, identity providers)

**Interface-Based Architecture**:
- `/aihub/core/`: Interfaces and abstract base classes (WHAT components must do)
- `/aihub/`: Concrete implementations (HOW components work)

**Dependency Injection**: All handlers receive clients via constructor injection

## Getting Started

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (for local development)
- PostgreSQL (or compatible database)
- Redis (for caching)
- Identity Provider credentials (Microsoft Entra ID, Google OAuth, etc.)

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/enricogoerlitz/aihub-backend.git
   cd aihub-backend
   ```

2. **Set up Python environment**
   ```bash
   # Using uv (recommended)
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -e .
   ```

3. **Start local infrastructure**
   ```bash
   docker-compose up -d
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

6. **Start the application**
   ```bash
   uvicorn aihub.app:app --reload
   ```

The API will be available at `http://localhost:8000`

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=aihub --cov-report=html

# Run in parallel
pytest -n auto
```

## Authentication & Authorization

### User Authentication

AIHub uses **identity provider integration** for authentication:

```http
Authorization: Bearer <jwt-token>
```

**Supported Providers**:
- Microsoft Entra ID
- Google OAuth
- Any OAuth 2.0/OIDC-compliant provider

### Permission Model

AIHub uses a two-tier permission system:

#### Tenant-Level Permissions
Assigned via `TenantMemberRole` table, multiple roles per member:

- `READER` — Read-only access to tenant resources
- `GLOBAL_ADMIN` — Full access to all tenant resources
- `CUSTOM_GROUPS_ADMIN` / `CUSTOM_GROUP_CREATOR` — Manage custom groups
- `APPLICATIONS_ADMIN` / `APPLICATIONS_CREATOR` — Manage applications
- `CREDENTIALS_ADMIN` / `CREDENTIALS_CREATOR` — Manage credentials
- `CONVERSATIONS_ADMIN` / `CONVERSATIONS_CREATOR` — Manage conversations
- `AUTONOMOUS_AGENTS_ADMIN` / `AUTONOMOUS_AGENTS_CREATOR` — Manage autonomous agents

#### Resource-Level Permissions
Assigned via `{Resource}Member` tables (Applications, Conversations, Credentials, etc.), one role per principal:

- `READ` — View resource and its data
- `WRITE` — Modify resource data
- `ADMIN` — Full control + manage permissions

#### Principal Types
- `IDENTITY_USER` — Individual user from identity provider
- `IDENTITY_GROUP` — Group from identity provider (Azure AD, etc.)
- `CUSTOM_GROUP` — Custom group defined in AIHub

**Permission Hierarchy**: ADMIN > WRITE > READ

## API Endpoints

All resource endpoints are tenant-scoped: `/api/v1/tenants/{tenant_id}/...`

### Tenants

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/tenants` | List all tenants |
| `POST` | `/api/v1/tenants` | Create new tenant |
| `GET` | `/api/v1/tenants/{tenant_id}` | Get tenant by ID |
| `PATCH` | `/api/v1/tenants/{tenant_id}` | Update tenant |
| `DELETE` | `/api/v1/tenants/{tenant_id}` | Delete tenant |
| `GET` | `/api/v1/tenants/{tenant_id}/principals` | List tenant members |
| `GET` | `/api/v1/tenants/{tenant_id}/principals/{principal_id}` | Get principal roles |
| `PUT` | `/api/v1/tenants/{tenant_id}/principals` | Set principal role |
| `DELETE` | `/api/v1/tenants/{tenant_id}/principals` | Remove principal role |

### Applications

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/tenants/{tenant_id}/applications` | List applications |
| `POST` | `/api/v1/tenants/{tenant_id}/applications` | Create application |
| `GET` | `/api/v1/tenants/{tenant_id}/applications/{application_id}` | Get application |
| `PATCH` | `/api/v1/tenants/{tenant_id}/applications/{application_id}` | Update application |
| `DELETE` | `/api/v1/tenants/{tenant_id}/applications/{application_id}` | Delete application |
| `GET` | `/api/v1/tenants/{tenant_id}/applications/{application_id}/principals` | List principals |
| `GET` | `/api/v1/tenants/{tenant_id}/applications/{application_id}/principals/{principal_id}` | Get principal permissions |
| `PUT` | `/api/v1/tenants/{tenant_id}/applications/{application_id}/principals` | Set principal permission |
| `DELETE` | `/api/v1/tenants/{tenant_id}/applications/{application_id}/principals` | Remove principal permission |

### Conversations

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/tenants/{tenant_id}/conversations` | List conversations |
| `POST` | `/api/v1/tenants/{tenant_id}/conversations` | Create conversation |
| `GET` | `/api/v1/tenants/{tenant_id}/conversations/{conversation_id}` | Get conversation |
| `PATCH` | `/api/v1/tenants/{tenant_id}/conversations/{conversation_id}` | Update conversation |
| `DELETE` | `/api/v1/tenants/{tenant_id}/conversations/{conversation_id}` | Delete conversation |
| `GET` | `/api/v1/tenants/{tenant_id}/conversations/{conversation_id}/principals` | List principals |
| `PUT` | `/api/v1/tenants/{tenant_id}/conversations/{conversation_id}/principals` | Set principal permission |
| `DELETE` | `/api/v1/tenants/{tenant_id}/conversations/{conversation_id}/principals` | Remove principal permission |

### Credentials

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/tenants/{tenant_id}/credentials` | List credentials |
| `POST` | `/api/v1/tenants/{tenant_id}/credentials` | Create credential |
| `GET` | `/api/v1/tenants/{tenant_id}/credentials/{credential_id}` | Get credential metadata |
| `PATCH` | `/api/v1/tenants/{tenant_id}/credentials/{credential_id}` | Update credential |
| `DELETE` | `/api/v1/tenants/{tenant_id}/credentials/{credential_id}` | Delete credential |
| `GET` | `/api/v1/tenants/{tenant_id}/credentials/{credential_id}/principals` | List principals |
| `PUT` | `/api/v1/tenants/{tenant_id}/credentials/{credential_id}/principals` | Set principal permission |
| `DELETE` | `/api/v1/tenants/{tenant_id}/credentials/{credential_id}/principals` | Remove principal permission |

### Autonomous Agents

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/tenants/{tenant_id}/autonomous-agents` | List autonomous agents |
| `POST` | `/api/v1/tenants/{tenant_id}/autonomous-agents` | Register new agent |
| `GET` | `/api/v1/tenants/{tenant_id}/autonomous-agents/{agent_id}` | Get autonomous agent |
| `PATCH` | `/api/v1/tenants/{tenant_id}/autonomous-agents/{agent_id}` | Update autonomous agent |
| `DELETE` | `/api/v1/tenants/{tenant_id}/autonomous-agents/{agent_id}` | Delete autonomous agent |
| `GET` | `/api/v1/tenants/{tenant_id}/autonomous-agents/{agent_id}/principals` | List principals |
| `PUT` | `/api/v1/tenants/{tenant_id}/autonomous-agents/{agent_id}/principals` | Set principal permission |
| `DELETE` | `/api/v1/tenants/{tenant_id}/autonomous-agents/{agent_id}/principals` | Remove principal permission |

### Custom Groups

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/tenants/{tenant_id}/custom-groups` | List custom groups |
| `POST` | `/api/v1/tenants/{tenant_id}/custom-groups` | Create custom group |
| `GET` | `/api/v1/tenants/{tenant_id}/custom-groups/{group_id}` | Get custom group |
| `PATCH` | `/api/v1/tenants/{tenant_id}/custom-groups/{group_id}` | Update custom group |
| `DELETE` | `/api/v1/tenants/{tenant_id}/custom-groups/{group_id}` | Delete custom group |
| `GET` | `/api/v1/tenants/{tenant_id}/custom-groups/{group_id}/principals` | List principals |
| `PUT` | `/api/v1/tenants/{tenant_id}/custom-groups/{group_id}/principals` | Set principal permission |
| `DELETE` | `/api/v1/tenants/{tenant_id}/custom-groups/{group_id}/principals` | Remove principal permission |

### Identity Provider

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/identity/me` | Get current user info |
| `GET` | `/api/v1/identity/me/tenants` | Get user's tenants |
| `GET` | `/api/v1/identity/me/groups` | Get user's groups |
| `GET` | `/api/v1/identity/provider/users` | List users from IdP |
| `GET` | `/api/v1/identity/provider/groups` | List groups from IdP |

For complete API documentation, visit `/docs` (Swagger UI) or `/redoc` after starting the server.

## Deployment Options

### SaaS
Fully managed cloud service with minimal setup and maintenance.

### Cloud Deployment
Deploy in your own cloud environment:
- **Azure**: Azure App Service, Azure Cosmos DB, Azure Key Vault
- **AWS**: ECS/EKS, DynamoDB/DocumentDB, Secrets Manager
- **GCP**: Cloud Run, Firestore, Secret Manager

### On-Premises
Run entirely within your data center for maximum security and compliance.

## Widget System

AIHub supports custom UI components embedded into chat conversations:

**Widget Delimiter**: `$%_WIDGET_%$`

Example LLM Response:
```
Please fill out this form:

$%_WIDGET_%$
{
    "type": "FORM",
    "structure": {
        "fields": [...]
    }
}
$%_WIDGET_%$

Thank you.
```

Widgets enable:
- Custom forms
- Data visualization
- Interactive components
- Specialized business logic

## Tracing & Observability

### Centralized Tracing
- **Unified database** for all agent traces
- **Semantic search** across conversations and agent outputs
- **Chat with traces**: Natural language queries about agent behavior

### Message Broker Architecture
External agents write tracing data to a message broker:
- **Asynchronous processing**: Non-blocking ingestion
- **Scalability**: Independent consumer microservice
- **Resilience**: Message buffering during outages

## Security Best Practices

1. **Always use HTTPS** in production
2. **Configure short token lifetimes** (1-4 hours)
3. **Implement refresh token rotation**
4. **Rotate autonomous agent keys regularly** (every 90 days)
5. **Use managed identities** for cloud deployments
6. **Apply principle of least privilege**
7. **Monitor failed authentication attempts**

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contact

**Author**: Enrico Goerlitz

For questions or support, please open an issue or contact the maintainers.

---

**AIHub** — Integrate your AI landscape. Unify your experience. Accelerate your innovation.
