# ADR 004: Handler Pattern for Business Logic

## Status

**Accepted** — 2025-12-07

## Context

The platform service manages 16+ resource types with CRUD operations, permission checks, caching, validation, and cross-resource dependencies. We need a consistent architecture that:

- Keeps route definitions thin and testable
- Centralizes business logic
- Supports FastAPI's dependency injection
- Maintains clear separation of concerns

## Decision

We adopt a strict **Handler Pattern** where:

### Rules

1. **Routes (`apis/v1/`)** are thin wrappers — they accept parameters, call a handler method, and return the response. Zero logic, zero data transformation.

2. **Handlers (`handlers/`)** contain all business logic — DB queries, permission checks, cache operations, validation, error handling.

3. **Dependencies (`handlers/dependencies/`)** provide FastAPI `Depends()` factories that inject configured handler instances with their required clients (DB, cache, vault).

### Structure per Resource

```
apis/v1/{resource}.py              # Routes (thin)
handlers/{resource}.py             # Business logic (Handler class)
handlers/dependencies/{resource}.py # Dependency injection factory
handlers/validators/{resource}_config.py  # Config validation (if needed)
schema/requests/{resource}.py      # Request Pydantic models
schema/responses/{resource}.py     # Response Pydantic models
exc/{resource}.py                  # Custom exceptions
core/database/models.py            # SQLAlchemy model + member model
```

### Shared Handlers

Cross-cutting concerns are handled by dedicated shared handlers:

| Handler | Responsibility |
|---------|---------------|
| `ResourcePermissionsHandler` | CRUD for resource-level permissions (member tables) |
| `ResourceTagsHandler` | CRUD for resource tags |
| `PermissionResolver` | Role-to-capability resolution |
| `PrincipalsHelper` | User/group principal resolution |

### Example Flow

```
POST /api/v1/tenants/{tid}/chat-agents
    → ChatAgentRoute.create()          # Route: extract params
        → ChatAgentHandler.create()     # Handler: validate, query DB, set permissions, cache
            → PermissionResolver.can_create()   # Check tenant role
            → db.add(ChatAgent(...))            # Create resource
            → ResourcePermissionsHandler.set()  # Set creator as ADMIN
            → CacheClient.invalidate()          # Invalidate cache
            → return ChatAgentResponse(...)     # Return typed response
```

## Consequences

### Positive

- Routes are trivially simple and rarely need modification
- Business logic is testable in isolation (mock DB/cache/vault)
- Consistent pattern across all 16+ resource types
- Dependency injection makes handler composition flexible
- Clear error boundaries via typed exceptions

### Negative

- Boilerplate-heavy for simple CRUD resources
- Handler files tend to grow large (several exceed 400-line limit)
- Adding a new resource type requires ~8 files (see project-structure instructions)

## Alternatives Considered

1. **Logic in routes** — Would create untestable, fat route files
2. **Service layer** — Semantically similar but "handler" better reflects the FastAPI pattern
3. **CQRS** — Overkill for current scale; most operations are simple CRUD
