---
applyTo: '**'
---

# unified-ui Project Specifications

## Project Overview
**unified-ui** is an integration platform for multiple AI agent systems with role-based access control (RBAC).

### Core Characteristics
- **Multi-Agent Integration**: Support for various agent systems (factory pattern)
- **Multi-Infrastructure**: Pluggable infrastructure components (databases, caching, vaults, identity providers)
- **Multi-Tenant**: Strict tenant isolation with granular permissions
- **Consistent Patterns**: Unified API structure, database schema patterns, and permission models

## Architecture

### Core Technologies
- **Framework**: FastAPI with Uvicorn
- **Language**: Python 3.x
- **Database Strategy**:
  - **PostgreSQL**: Relational data (tenants, permissions, applications, conversations, credentials, custom groups)
  - **JSON/Document DB**: Messages, traces (access by ID only)
- **Caching**: Redis with tenant-based cache invalidation
- **Identity**: Azure AD integration via MSAL
- **Secrets Management**: Azure Key Vault
- **Message Broker**: RabbitMQ/Kafka (for async operations)

### Project Structure
```
aihub/
├── app.py              # FastAPI application entry point
├── logger.py           # Centralized logging
├── apis/v1/            # API route definitions (NO business logic!)
├── handlers/           # Business logic handlers (ALL business logic!)
├── schema/             # Pydantic schemas
├── core/               # Core interfaces and base implementations
│   ├── database/       # Database models, interfaces, base clients
│   ├── vault/          # Vault interfaces
│   ├── caching/        # Caching interfaces
│   └── identity/       # Identity provider interfaces
├── database/           # Concrete database implementations (PostgreSQL, etc.)
├── caching/            # Concrete caching implementations (Redis, etc.)
├── vault/              # Concrete vault implementations (Azure Key Vault, etc.)
├── identity/           # Concrete identity provider implementations
├── docdatabase/        # Document database client
├── message_broker/     # Message broker integration
├── exc/                # Custom exceptions
├── libs/               # Shared libraries
└── utils/              # Utility functions
```

### Core vs Implementation Pattern
- **/aihub/core/**: Interfaces, abstract base classes, core models
  - Defines **WHAT** components must do
  - Database-agnostic, infrastructure-agnostic
  - Example: `core/vault/interface.py` defines `IVaultClient`
- **/aihub/**: Concrete implementations
  - Defines **HOW** components work
  - Same folder structure as `core/`
  - Example: `vault/keyvault.py` implements `IVaultClient` for Azure Key Vault
  - Example: `vault/hashicorp.py` implements `IVaultClient` for HashiCorp Vault

## Code Standards

### Design Patterns

#### Factory Pattern (Core Pattern)
- Use factory pattern extensively for:
  - Agent system integrations (OpenAI Agents, LangChain, CrewAI, etc.)
  - Infrastructure components (databases, caches, vaults, identity providers)
- Factory classes select concrete implementations at runtime

#### Critical Rules
- **ALL BUSINESS LOGIC** goes in handlers - never in routes!
- Handle all data processing, validation, transformations
- Orchestrate database, cache, vault operations
- Apply permission filtering in list operations

#### Standard Handler Pattern
```python
class ResourceHandler:
    def __init__(self, db_client, cache_client, vault_client):
        self.db = db_client
        self.cache = cache_client
        self.vault = vault_client
    
    async def list_resources(
        self, 
        tenant_id: str, 
        user: IdentityUser, 
        skip: int, 
        limit: int
    ):
        # IMPORTANT: Filter by user permissions via member join!
        # User only sees resources they have access to
        query = (
            select(Resource)
            .join(ResourceMember)
            .where(
                ResourceMember.principal_id == user.id,
                Resource.tenant_id == tenant_id
            )
            .offset(skip)
            .limit(limit)
        )
        return await self.db.execute(query)
```

#### List Operations - Critical Pattern
- **ALWAYS** join with `{resource}_members` table
- **ALWAYS** filter by `principal_id == user.id`
- Users only see resources they have explicit access to
- Exception: Tenant admins may see all resources (check tenant role first)

#### Dependency Injection
Use dependency injection for:
- Database clients
- Cache clients
- Vault clients
- Identity providers

Never initialize these in handlers - always inject via constructor or function parameters.

#### Return Values
- Return Pydantic schemas
- Handle exceptions and convert to appropriate HTTP responses
- Use custom exceptions from `exc/`
              return HashiCorpVaultClient()
  ```

### API Routes (`apis/v1/`)

#### Critical Rules
- **NO BUSINESS LOGIC** in route files - only in handlers!
- Routes only:
  1. Accept request parameters (query, path, body)
  2. Call handler with parameters
  3. Return handler response
- Use dependency injection for handlers
- Keep routes thin - delegate everything to handlers

#### Standard Route Patterns
All resource routes follow this pattern:

**Collection Routes:**
```
GET  /api/v1/tenants/{tenant_id}/{resource}
POST /api/v1/tenants/{tenant_id}/{resource}
```

**Item Routes:**
```rchitecture

#### Core Database (PostgreSQL)
Stores all structured, relational data with consistent patterns.

**Core Database Tables:**
- Tenants, TenantMembers, TenantMemberRoles
- CustomGroups, CustomGroupMembers
- Applications, ApplicationMembers
- Conversations, ConversationMembers
- AutonomousAgents, AutonomousAgentMembers
- Credentials, CredentialMembers

#### Standard Database Pattern (The Sacred Pattern)

**Every resource (except Tenants) follows this exact structure:**

1. **Resource Table**: Main entity table
   - `id`, `name`, `description`, `tenant_id`
   - Audit fields: `created_at`, `updated_at`, `created_by`, `updated_by`
   - Additional resource-specific fields (e.g., `config` for Applications)

2. **ResourceMember Table**: Permission table
   - `id`, `{resource}_id`, `principal_id`, `principal_type`, `role`, `tenant_id`
   - Audit fields
   - Unique constraint on `({resource}_id, principal_id, principal_type)`
   - **role**: ALWAYS one of `READ`, `WRITE`, `ADMIN` (PermissionActionEnum)

**Example Schema:**
```python
class Application(Base, IdNameDescriptionMixin, TenantScopedMixin):
    __tablename__ = "applications"
    config: Mapped[dict] = mapped_column(PortableJSON, nullable=False, default=dict)
    members: Mapped[list["ApplicationMember"]] = relationship(...)

class ApplicationMember(Base, IdMixin, AuditMixin):
    __tablename__ = "application_members"
    tenant_id: Mapped[str] = mapped_column(...)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)
    principal_type: Mapped[str] = mapped_column(PrincipalTypeSAEnum, nullable=False)
    role: Mapped[str] = mapped_column(PermissionActionSAEnum, nullable=False)  # READ | WRITE | ADMIN
```

#### Tenant Special Case
- Tenants have a different permission model
- `TenantMemberRole` allows **mul

#### Standard Principal Response Schema
**CRITICAL**: All `/principals` endpoints use consistent response schemas:

```python
class PrincipalRoleResponse(BaseModel):
    """Standard response for principal permissions."""
    principal_id: str
    principal_type: PrincipalTypeEnum  # USER | IDENTITY_GROUP | CUSTOM_GROUP
    role: PermissionActionEnum  # READ | WRITE | ADMIN
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]
    updated_by: Optional[str]

class PrincipalListResponse(BaseModel):
    """Standard response for listing principals."""
    principals: list[PrincipalRoleResponse]
    total: int
```

- Use this schema for ALL resources (applications, conversations, credentials, etc.)
- Only exception: Tenant principals (use `TenantMemberResponse` with multiple roles)tiple roles per member**
- Roles defined in `TenantPermissionEnum` (not PermissionActionEnum)
- This is the ONLY exception to the standard pattern

#### Document Database
- **Use for**: Messages, traces (high-volume, ID-based access only)
- **Access pattern**: Get by ID or get multiple by parent ID
- **Not for**: Queryable, filterable data

#### Database Access Rules

#### Permission Model Overview
- **Entities**: Tenants, Applications, Conversations, Credentials, Autonomous Agents, Custom Groups
- **Roles**: Always use enums (never string names)
- **Permission Storage**: `{entity}_members` tables
- **Permission Validation**: Middleware decorator (`check_permissions`)

#### Standard Permission Roles (PermissionActionEnum)
Used for ALL resources except Tenants:
- **READ**: View resource and its data
- **WRITE**: Modify resource data
- **ADMIN**: Full control + manage permissions

#### Principal Types (PrincipalTypeEnum)
- **USER**: Individual user from identity provider
- **IDENTITY_GROUP**: Group from identity provider (Azure AD, Okta, etc.)
- **CUSTOM_GROUP**: Custom group defined in AIHub

#### Permission Check Pattern
```python
@check_permissions(required_role=PermissionActionEnum.WRITE)
async def update_resource(resource_id: str, user: IdentityUser):
    # Middleware validates:
    # 1. User has WRITE or ADMIN role on this specific resource_id
    # 2. Resource belongs to user's tenant
    pass
```

#### Authorization Flow
1. Extract user from JWT token
2. Check tenant membership (is user in this tenant?)
3. Check resource permission (does user have required role on this resource?)
4. For list operations: Filter results by user's accessible resources

#### Permission Hierarchy
- **ADMIN** > **WRITE** > **READ**
- ADMIN can do everything WRITE and READ can do
- WRITE can do everything READ can do
GET    /api/v1/tenants/{tenant_id}/{resource}/{resource_id}/principals/{principal_id}
DELETE /api/v1/tenants/{tenant_id}/{resource}/{resource_id}/principals/{principal_id}
```

#### Example Route (Correct)
```python
@router.get("/tenants/{tenant_id}/applications")
async def list_applications(
    tenant_id: str,
    skip: int = 0,
    limit: int = 100,
    handler: ApplicationHandler = Depends(get_application_handler),
    user: IdentityUser = Depends(get_current_user),
):
    # NO business logic - just call handler
    return await handler.list_applications(tenant_id, user, skip, limit)
```

### Handlers (`handlers/`)
- All business logic goes here
- Use dependency injection for:
  - Database clients
  - Cache clients
  - Vault clients
  - Identity providers
- Return Pydantic schemas
- Handle exceptions and convert to HTTP responses

### Schemas (`schema/`)
- Use Pydantic models for all request/response data
- Separate schemas for:
  - Request bodies
  - Response bodies
  - Database models
- Include validators where needed

### Database Access
- **PostgreSQL**: For structured, queryable data
  - Tenants, permissions, applications, conversations, credentials
  - Use SQLAlchemy or similar ORM
  - All queries through core database clients
- **Document DB**: For high-volume, ID-based access
  - Messages, traces
  - Access pattern: get by ID or get multiple by parent ID
- Never initialize DB clients in route handlers - always inject

### Caching Strategy
- **Cache Key Pattern**: `{tenant_id}:{resource}:{id}`
- **User Cache Pattern**: `user:{user_id}:{resource}`
- **Cache Invalidation**:
  - Permissions changed → clear `*user:{user_id}*`
  - Tenant data changed → clear `{tenant_id}:*`
  - Resource updated → clear specific key
- Use Redis client through dependency injection
- Cache encryption for sensitive data (use env var for encryption key)

### Authentication & Authorization

#### Authentication Flow
- **Identity Provider**: Factory-based (Azure AD, Okta, etc.)
- **Token**: JWT Bearer token in `Authorization` header
- **User Context**: `ContextIdentityUser` object with lazy-loaded properties
- **Middleware**: `@authenticate` decorator validates token and injects user

#### ContextIdentityUser Structure
```python
class ContextIdentityUser:
    identity: IdentityUser        # User ID, email, tenant ID from token
    groups: list[IdentityGroupResponse]      # Identity provider groups (cached)
    custom_groups: list[CustomGroupResponse] # AIHub custom groups (cached)
    tenants: list[TenantResponse]            # User's tenants with roles (cached)
```

#### Authorization Middleware
- **@authenticate**: Validates token, creates ContextIdentityUser, stores in `request.state.user`
- **@check_permissions**: Validates user has required role on specific resource
- Cache header: `X-Use-Cache: true|false` controls caching behavior

#### Permission Check Decorator
```python
@check_permissions(
    resource_type="application",  # applications, conversations, credentials, etc.
    required_role=PermissionActionEnum.WRITE,
    resource_id_param="application_id"  # Path parameter name
)
async def update_application(application_id: str, ...):
    # Decorator ensures user has WRITE or ADMIN on this application
    pass
```

#### Tenant-Level Admin Permissions
Certain tenant roles bypass resource-level checks:
- **GLOBAL_ADMIN**: Full access to all resources in tenant
- **{RESOURCE}_ADMIN**: Full access to specific resource type (e.g., APPLICATIONS_ADMIN)
- Check these BEFORE filtering by resource permissions in list operations

### Permissions & RBAC
- **Entities**: Tenants, Applications, Conversations, Credentials, Autonomous Agents
- **Roles**: Define roles as enums (not string names)
- **Permission Model**: `entity_members` with role assignments
- **Permission Validation**: Decorator-based (`@requires_permission`)
- Check both:
  1. User has required role/permission
  2. User has access to specific resource ID

### Secrets Management
- Store sensitive data in Azure Key Vault
- **Credentials**:
  - Metadata in PostgreSQL
  - Actual secrets in vault
  - Cache decrypted secrets with encryption layer
- Never log secrets or credentials

### Error Handling
- Use custom exceptions from `exc/`
- Exception hierarchy:
  - `BaseError`: Base exception class
  - Resource-specific: `ApplicationNotFoundError`, `TenantNotFoundError`, etc.
  - Permission errors: `PermissionDeniedError`, `UnauthorizedError`
- Convert exceptions to appropriate HTTP status codes in handlers
- Return consistent error response format:
  ```python
  {
      "detail": "Resource not found",
      "error_code": "RESOURCE_NOT_FOUND",
      "status_code": 404
  }
  ```
- Log errors with context (tenant_id, user_id, trace_id)

### Logging
- Use centralized logger from `logger.py`
- Include context: `tenant_id`, `user_id`, `request_id`
- Log levels:
  - DEBUG: Development details
  - INFO: Business events
  - WARNING: Recoverable issues
  - ERROR: Application errors
  - CRITICAL: System failures

## Integration Points

### N8N Workflow Integration
- Applications have N8N connection config
- Invoke workflows via HTTP API
- Handle async responses via message broker

### Message Broker
- Use for async operations
- Event-driven architecture for:
  - Conversation events
  - Agent invocations
  - Background tasks

## Configuration
- Use environment variables for all config
- Never hardcode credentials or endpoints
- Support multiple environments (dev, test, prod)

## Migration & Database
- Use Alembic for database migrations
- Keep migrations in `alembic/versions/`
- Test migrations in both directions (up/down)

## Development Workflow
- Feature branches: `feature/{feature-name}`
- Run tests before committing
- Use pytest for all tests
- Code coverage minimum: 80%

## Performance Considerations
- Cache frequently accessed data
- Use async/await where possible
- Optimize database queries (avoid N+1)
- Monitor Redis cache hit rates
- Use connection pooling for databases

## Security
- Validate all inputs (Pydantic schemas)
- Sanitize data before database operations
- Use parameterized queries (prevent SQL injection)
- Rate limiting on API endpoints
- Audit logging for sensitive operations

## Next Link Pattern
- Support pagination with `next_link` for list operations
- Test Graph API `next_link` functionality
- Implement in user listings and group listings
