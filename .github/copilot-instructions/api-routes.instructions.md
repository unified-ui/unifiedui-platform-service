# API Routes

## Location
All API route files are in `unifiedui/apis/v1/`.

---

## Golden Rule: Routes are THIN WRAPPERS

Routes must contain **ZERO business logic**. They only:
1. Accept request parameters (path, query, body via Pydantic)
2. Extract authenticated user from `request.state.user`
3. Call the handler method
4. Catch handler exceptions → map to `HTTPException` with correct status code

---

## Route File Template

```python
"""API routes for {resource_name} management."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query

from unifiedui.core.identity.users import ContextIdentityUser
from unifiedui.handlers.{resource_name} import {Resource}Handler
from unifiedui.handlers.dependencies import get_{resource}_handler
from unifiedui.schema.requests.{resource_name} import Create{Resource}Request, Update{Resource}Request
from unifiedui.schema.responses.{resource_name} import {Resource}Response
from unifiedui.exc.{resource_name} import {Resource}NotFoundError
from unifiedui.core.middleware.apis.v1.auth import authenticate, check_permissions
from unifiedui.core.database.enums import TenantRolesEnum, PermissionActionEnum, OrderDirectionEnum, ListViewEnum
from unifiedui.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/{resource_name_plural}")


@router.get("")
@authenticate()
async def list_{resource_name_plural}(
    request: Request,
    tenant_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    name: Optional[str] = Query(None),
    order_by: Optional[str] = Query(None),
    order_direction: Optional[OrderDirectionEnum] = Query(None),
    view: Optional[ListViewEnum] = Query(None),
    handler: {Resource}Handler = Depends(get_{resource}_handler)
):
    try:
        user: ContextIdentityUser = request.state.user
        return handler.list_{resource_name_plural}(tenant_id=tenant_id, user=user, skip=skip, limit=limit, ...)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list {resource_name_plural}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list {resource_name_plural}")


@router.post("", status_code=status.HTTP_201_CREATED)
@authenticate()
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.{RESOURCE}_ADMIN,
        TenantRolesEnum.{RESOURCE}_CREATOR
    ]
)
async def create_{resource}(
    request: Request,
    tenant_id: str,
    create_request: Create{Resource}Request,
    handler: {Resource}Handler = Depends(get_{resource}_handler)
):
    try:
        user: ContextIdentityUser = request.state.user
        return handler.create_{resource}(tenant_id=tenant_id, request=create_request, ...)
    except {Resource}NotFoundError:
        raise HTTPException(status_code=404, detail="{Resource} not found")
    ...
```

---

## Decorator Stacking Order

Decorators must be applied in this exact order:
```python
@router.get("")                    # 1. Route definition
@authenticate()                    # 2. Authentication (always)
@check_permissions(entity=...,     # 3. Permission check (if needed)
    required_permissions=[...])
async def handler(...):
```

---

## Standard URL Patterns

All routes are prefixed at registration: `/api/v1/platform-service/tenants/{tenant_id}/`

| Pattern | HTTP | Description |
|---------|------|-------------|
| `/{resources}` | GET | List resources (permission-filtered) |
| `/{resources}` | POST | Create resource |
| `/{resources}/{resource_id}` | GET | Get resource detail |
| `/{resources}/{resource_id}` | PATCH | Update resource |
| `/{resources}/{resource_id}` | DELETE | Delete resource |
| `/{resources}/{resource_id}/principals` | GET | List resource permissions |
| `/{resources}/{resource_id}/principals` | PUT | Set/add permission |
| `/{resources}/{resource_id}/principals` | DELETE | Remove permission |
| `/{resources}/{resource_id}/principals/{principal_id}` | GET | Get principal's permission |

---

## Standard Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `skip` | int | 0 | Pagination offset |
| `limit` | int | 100 | Items per page (max 1000) |
| `name` | str | None | Filter by name (ilike) |
| `is_active` | int | None | Filter by active status (0/1) |
| `tags` | str | None | Comma-separated tag IDs |
| `order_by` | str | None | Column to sort by |
| `order_direction` | OrderDirectionEnum | None | `asc` or `desc` |
| `view` | ListViewEnum | None | `full` or `quick-list` |

---

## Exception Mapping Pattern

```python
try:
    result = handler.do_something(...)
    return result
except {Resource}NotFoundError:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="...")
except {Resource}ConfigValidationError as e:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
except UnsupportedApplicationTypeError as e:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
except InvalidCredentialError as e:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
except HTTPException:
    raise  # Always re-raise HTTPExceptions from auth decorators
except Exception as e:
    logger.error(f"Failed: {e}")
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="...")
```

---

## Registering New Routes

In `app.py`, register the router:
```python
from unifiedui.apis.v1 import new_resource

app.include_router(
    new_resource.router,
    prefix="/api/v1/platform-service/tenants/{tenant_id}",
    tags=["New Resource"]
)
```

---

## Special Auth Patterns

### API Key Authentication (Autonomous Agents)
```python
@router.post("/{autonomous_agent_id}/validate-api-key")
@authenticate_autonomous_agent_api_key()
async def validate_api_key(request: Request, tenant_id: str, autonomous_agent_id: str):
    # No Bearer token — uses X-Unified-UI-Autonomous-Agent-API-Key header
    ...
```

### Service-to-Service Authentication (Bearer + Service Key)
```python
@router.get("/{resource_id}/config")
@authenticate(required_service_auth_key="AGENT_TO_PLATFORM_SERVICE_KEY")
@check_permissions(entity="resource", required_permissions=[PermissionActionEnum.READ])
async def get_config(request: Request, ...):
    # Requires BOTH X-Service-Key header AND Bearer token
    ...
```

### Service-to-Service Authentication (Service Key Only)
```python
@router.get("/by-purpose/{purpose_group}")
@authenticate_service_key(required_service_auth_key="AGENT_TO_PLATFORM_SERVICE_KEY")
async def get_models_by_purpose(request: Request, tenant_id: str, purpose_group: str, ...):
    # Requires ONLY X-Service-Key header — no Bearer token, no user context
    # Used for S2S-only endpoints (e.g., AI model lookup by agent-service)
    ...
```

---

## Non-Standard Resources

### TenantAIModel (S2S-only, no RBAC)
- No `@check_permissions()` — all endpoints use `@authenticate()` or `@authenticate_service_key()`
- No member table — scoped only by tenant
- CRUD by tenant admin users via `@authenticate()`, lookup by purpose via `@authenticate_service_key()`
- Routes registered at: `/api/v1/platform-service/tenants/{tenant_id}/ai-models`

### ReACT Agent (Standard RBAC Resource)
- Full CRUD + permission management + tags support
- Same decorator pattern as Application/AutonomousAgent (authenticate + check_permissions)
- Routes registered at: `/api/v1/platform-service/tenants/{tenant_id}/re-act-agents`

### Dashboard (Aggregation endpoint)
- `GET /dashboard/stats` — returns aggregated counts (total + active) for applications, autonomous_agents, conversations
- RBAC-filtered: only counts entities the user has access to
- Cached for 120s via Redis
- Routes registered at: `/api/v1/platform-service/tenants/{tenant_id}/dashboard`

### Global Search
- `GET /search?q=...&types=...&limit=10` — searches across applications, autonomous_agents, conversations, credentials by name (ILIKE)
- RBAC-filtered: only returns entities the user has access to
- Routes registered at: `/api/v1/platform-service/tenants/{tenant_id}/search`

### Recent Visits
- `GET /users/{user_id}/recent-visits` — list user's recent visits (up to 50)
- `POST /users/{user_id}/recent-visits/sync` — sync visits from client (upsert + cleanup)
- Routes registered at: `/api/v1/platform-service/tenants/{tenant_id}/recent-visits`
