"""API routes for external app management."""

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response

from unifiedui.core.database.enums import OrderDirectionEnum, TenantRolesEnum
from unifiedui.core.middleware.apis.v1.auth import authenticate, check_permissions
from unifiedui.handlers.dependencies import get_external_app_handler
from unifiedui.handlers.external_apps import ExternalAppHandler
from unifiedui.logger import get_logger
from unifiedui.schema.requests.external_apps import CreateExternalAppRequest, UpdateExternalAppRequest
from unifiedui.schema.responses.external_apps import ExternalAppResponse

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser

logger = get_logger(__name__)

router = APIRouter(prefix="/external-apps")


@router.get(
    "",
    summary="List external apps",
    description="Get a paginated list of external apps for the current tenant.",
)
@authenticate()
async def list_external_apps(
    request: Request,
    tenant_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return"),
    name: str | None = Query(None, description="Filter by app name"),
    order_by: str | None = Query(
        None, description="Column name to order by (e.g., 'name', 'created_at', 'updated_at')"
    ),
    order_direction: OrderDirectionEnum | None = Query(None, description="Sort direction: 'asc' or 'desc'"),
    handler: ExternalAppHandler = Depends(get_external_app_handler),
) -> list[ExternalAppResponse]:
    """List external apps for a tenant."""
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: List external apps",
            extra={"tenant_id": tenant_id, "user_id": user.identity.get_id(), "skip": skip, "limit": limit},
        )
        return handler.list_external_apps(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            name_filter=name,
            order_by=order_by,
            order_direction=order_direction.value if order_direction else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list external apps: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list external apps")


@router.get(
    "/{external_app_id}",
    response_model=ExternalAppResponse,
    summary="Get external app",
    description="Get a specific external app by ID.",
)
@authenticate()
async def get_external_app(
    request: Request,
    tenant_id: str,
    external_app_id: str,
    handler: ExternalAppHandler = Depends(get_external_app_handler),
) -> ExternalAppResponse:
    """Get a specific external app."""
    user: ContextIdentityUser = request.state.user
    logger.info(
        "API: Get external app",
        extra={"tenant_id": tenant_id, "user_id": user.identity.get_id(), "external_app_id": external_app_id},
    )
    return handler.get_external_app(tenant_id=tenant_id, external_app_id=external_app_id)


@router.post(
    "",
    response_model=ExternalAppResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create external app",
    description="Create a new external app.",
)
@authenticate()
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.EXTERNAL_APPS_ADMIN,
        TenantRolesEnum.EXTERNAL_APPS_CREATOR,
    ],
)
async def create_external_app(
    request: Request,
    tenant_id: str,
    create_request: CreateExternalAppRequest,
    handler: ExternalAppHandler = Depends(get_external_app_handler),
) -> ExternalAppResponse:
    """Create a new external app."""
    user: ContextIdentityUser = request.state.user
    logger.info(
        "API: Create external app",
        extra={"tenant_id": tenant_id, "user_id": user.identity.get_id(), "app_name": create_request.name},
    )
    return handler.create_external_app(tenant_id=tenant_id, request=create_request, user_id=user.identity.get_id())


@router.patch(
    "/{external_app_id}",
    response_model=ExternalAppResponse,
    summary="Update external app",
    description="Update an existing external app.",
)
@authenticate()
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.EXTERNAL_APPS_ADMIN,
    ],
)
async def update_external_app(
    request: Request,
    tenant_id: str,
    external_app_id: str,
    update_request: UpdateExternalAppRequest,
    handler: ExternalAppHandler = Depends(get_external_app_handler),
) -> ExternalAppResponse:
    """Update an external app."""
    user: ContextIdentityUser = request.state.user
    logger.info(
        "API: Update external app",
        extra={"tenant_id": tenant_id, "user_id": user.identity.get_id(), "external_app_id": external_app_id},
    )
    return handler.update_external_app(
        tenant_id=tenant_id, external_app_id=external_app_id, request=update_request, user_id=user.identity.get_id()
    )


@router.delete(
    "/{external_app_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete external app",
    description="Delete an external app.",
)
@authenticate()
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.EXTERNAL_APPS_ADMIN,
    ],
)
async def delete_external_app(
    request: Request,
    tenant_id: str,
    external_app_id: str,
    handler: ExternalAppHandler = Depends(get_external_app_handler),
) -> Response:
    """Delete an external app."""
    user: ContextIdentityUser = request.state.user
    logger.info(
        "API: Delete external app",
        extra={"tenant_id": tenant_id, "user_id": user.identity.get_id(), "external_app_id": external_app_id},
    )
    handler.delete_external_app(tenant_id=tenant_id, external_app_id=external_app_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
