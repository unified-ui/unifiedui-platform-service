"""API routes for external app management."""

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, Response

from unifiedui.core.database.enums import OrderDirectionEnum, PermissionActionEnum, TenantRolesEnum
from unifiedui.core.middleware.apis.v1.auth import authenticate, check_permissions
from unifiedui.handlers.dependencies import get_external_app_handler
from unifiedui.handlers.external_apps import ExternalAppHandler
from unifiedui.handlers.field_filter import filtered_response, parse_ids
from unifiedui.logger import get_logger
from unifiedui.schema.requests.external_apps import CreateExternalAppRequest, UpdateExternalAppRequest
from unifiedui.schema.requests.permissions import SetResourcePermissionRequest
from unifiedui.schema.responses.external_apps import ExternalAppResponse
from unifiedui.schema.responses.principals import PrincipalWithRolesResponse, ResourcePrincipalsResponse

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
    tags: str | None = Query(None, description="Comma-separated list of tag IDs to filter by (OR logic)"),
    order_by: str | None = Query(
        None, description="Column name to order by (e.g., 'name', 'created_at', 'updated_at')"
    ),
    order_direction: OrderDirectionEnum | None = Query(None, description="Sort direction: 'asc' or 'desc'"),
    ids: str | None = Query(None, description="Comma-separated list of IDs to filter by"),
    fields: str | None = Query(None, description="Comma-separated list of fields to include in the response"),
    handler: ExternalAppHandler = Depends(get_external_app_handler),
) -> list[ExternalAppResponse] | JSONResponse:
    """List external apps for a tenant."""
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: List external apps",
            extra={"tenant_id": tenant_id, "user_id": user.identity.get_id(), "skip": skip, "limit": limit},
        )
        tag_ids = [int(t.strip()) for t in tags.split(",") if t.strip()] if tags else None
        return filtered_response(
            handler.list_external_apps(
                tenant_id=tenant_id,
                user=user,
                skip=skip,
                limit=limit,
                name_filter=name,
                tag_ids=tag_ids,
                order_by=order_by,
                order_direction=order_direction.value if order_direction else None,
                id_list=parse_ids(ids),
            ),
            fields,
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
@check_permissions(
    entity="external_app",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.EXTERNAL_APPS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ,
    ],
)
async def get_external_app(
    request: Request,
    tenant_id: str,
    external_app_id: str,
    fields: str | None = Query(None, description="Comma-separated list of fields to include in the response"),
    handler: ExternalAppHandler = Depends(get_external_app_handler),
) -> ExternalAppResponse | JSONResponse:
    """Get a specific external app."""
    user: ContextIdentityUser = request.state.user
    logger.info(
        "API: Get external app",
        extra={"tenant_id": tenant_id, "user_id": user.identity.get_id(), "external_app_id": external_app_id},
    )
    return filtered_response(
        handler.get_external_app(tenant_id=tenant_id, external_app_id=external_app_id, user=user),
        fields,
    )


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
    return handler.create_external_app(
        tenant_id=tenant_id, request=create_request, user_id=user.identity.get_id(), user=user
    )


@router.patch(
    "/{external_app_id}",
    response_model=ExternalAppResponse,
    summary="Update external app",
    description="Update an existing external app.",
)
@authenticate()
@check_permissions(
    entity="external_app",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.EXTERNAL_APPS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
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
    entity="external_app",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.EXTERNAL_APPS_ADMIN,
        PermissionActionEnum.ADMIN,
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


# ========== External App Permission Endpoints ==========


@router.get(
    "/{external_app_id}/principals",
    response_model=ResourcePrincipalsResponse,
    summary="List external app permissions",
    description="Get all principals with permissions for an external app",
)
@authenticate()
@check_permissions(
    entity="external_app",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.EXTERNAL_APPS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ,
    ],
)
async def list_external_app_permissions(
    request: Request,
    tenant_id: str,
    external_app_id: str,
    skip: int = Query(0, ge=0, description="Number of principals to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of principals to return"),
    search: str | None = Query(None, description="Search term for display_name, principal_name, or mail"),
    roles: str | None = Query(None, description="Comma-separated roles to filter by (OR logic)"),
    is_active: bool | None = Query(None, description="Filter by is_active status"),
    order_by: str | None = Query(None, enum=["display_name"], description="Column to order by"),
    order_direction: str | None = Query("asc", enum=["asc", "desc"], description="Sort direction"),
    handler: ExternalAppHandler = Depends(get_external_app_handler),
) -> ResourcePrincipalsResponse:
    """List all permissions for an external app."""
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: List external app permissions",
            extra={"tenant_id": tenant_id, "external_app_id": external_app_id, "user_id": user.identity.get_id()},
        )

        roles_list = [r.strip() for r in roles.split(",")] if roles else None

        return handler.list_external_app_permissions(
            tenant_id=tenant_id,
            external_app_id=external_app_id,
            skip=skip,
            limit=limit,
            search=search,
            roles=roles_list,
            is_active=is_active,
            order_by=order_by,
            order_direction=order_direction,
        )
    except Exception as e:
        logger.error("Failed to list external app permissions: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list external app permissions"
        )


@router.get(
    "/{external_app_id}/principals/{principal_id}",
    response_model=PrincipalWithRolesResponse,
    summary="Get external app permissions for principal",
    description="Get all permissions for a specific principal on an external app",
)
@authenticate()
@check_permissions(
    entity="external_app",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.EXTERNAL_APPS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ,
    ],
)
async def get_external_app_permission(
    request: Request,
    tenant_id: str,
    external_app_id: str,
    principal_id: str,
    handler: ExternalAppHandler = Depends(get_external_app_handler),
) -> PrincipalWithRolesResponse:
    """Get all permissions for a specific principal on an external app."""
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Get external app permission",
            extra={
                "tenant_id": tenant_id,
                "external_app_id": external_app_id,
                "principal_id": principal_id,
                "user_id": user.identity.get_id(),
            },
        )
        return handler.get_external_app_permission(
            tenant_id=tenant_id, external_app_id=external_app_id, principal_id=principal_id
        )
    except Exception as e:
        logger.error("Failed to get external app permission: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get external app permission"
        )


@router.put(
    "/{external_app_id}/principals",
    response_model=PrincipalWithRolesResponse,
    summary="Set external app permission",
    description="Set or update a principal's permission for an external app",
)
@authenticate()
@check_permissions(
    entity="external_app",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.EXTERNAL_APPS_ADMIN,
        PermissionActionEnum.ADMIN,
    ],
)
async def set_external_app_permission(
    request: Request,
    tenant_id: str,
    external_app_id: str,
    permission_request: SetResourcePermissionRequest,
    handler: ExternalAppHandler = Depends(get_external_app_handler),
) -> PrincipalWithRolesResponse:
    """Set or update an external app permission."""
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Set external app permission",
            extra={
                "tenant_id": tenant_id,
                "external_app_id": external_app_id,
                "principal_id": permission_request.principal_id,
                "user_id": user.identity.get_id(),
            },
        )
        return handler.set_external_app_permission(
            tenant_id=tenant_id,
            external_app_id=external_app_id,
            request=permission_request,
            user_id=user.identity.get_id(),
            user=user,
        )
    except Exception as e:
        logger.error("Failed to set external app permission: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to set external app permission: {e!s}"
        )


@router.delete(
    "/{external_app_id}/principals",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete external app permission",
    description="Remove a principal's permission for an external app",
)
@authenticate()
@check_permissions(
    entity="external_app",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.EXTERNAL_APPS_ADMIN,
        PermissionActionEnum.ADMIN,
    ],
)
async def delete_external_app_permission(
    request: Request,
    tenant_id: str,
    external_app_id: str,
    delete_request: SetResourcePermissionRequest,
    handler: ExternalAppHandler = Depends(get_external_app_handler),
) -> Response:
    """Delete an external app permission."""
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Delete external app permission",
            extra={
                "tenant_id": tenant_id,
                "external_app_id": external_app_id,
                "principal_id": delete_request.principal_id,
                "user_id": user.identity.get_id(),
            },
        )
        handler.delete_external_app_permission(
            tenant_id=tenant_id,
            external_app_id=external_app_id,
            principal_id=delete_request.principal_id,
            principal_type=delete_request.principal_type.value,
            permission=delete_request.role.value,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.error("Failed to delete external app permission: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete external app permission"
        )
