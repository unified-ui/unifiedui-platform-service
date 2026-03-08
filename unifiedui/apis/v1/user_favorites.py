"""API routes for user favorites management."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response

from unifiedui.core.database.enums import UserPermissionEnum
from unifiedui.core.middleware.apis.v1.auth import authenticate, check_permissions
from unifiedui.handlers.dependencies import get_user_favorites_handler
from unifiedui.handlers.user_favorites import UserFavoritesHandler
from unifiedui.logger import get_logger
from unifiedui.schema.responses.user_favorites import UserFavoriteResponse, UserFavoritesListResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/users/{user_id}/favorites")


@router.get(
    "/{resource_type}",
    response_model=UserFavoritesListResponse,
    summary="List user favorites",
    description="Get a list of user favorites for a specific resource type",
)
@authenticate()
@check_permissions(entity="user_favorite", required_permissions=[UserPermissionEnum.IS_CREATOR])
async def list_user_favorites(
    request: Request,
    tenant_id: str,
    user_id: str,
    resource_type: str,
    handler: UserFavoritesHandler = Depends(get_user_favorites_handler),
) -> UserFavoritesListResponse:
    """
    List user favorites for a specific resource type.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        user_id: User ID from path
        resource_type: Type of resource (chat-agents, autonomous-agents, development-platforms, conversations)
        handler: User favorites handler dependency

    Returns:
        List of user favorites
    """
    try:
        use_cache = request.headers.get("X-Use-Cache", "true").lower() == "true"

        logger.info(
            "API: List user favorites",
            extra={"tenant_id": tenant_id, "user_id": user_id, "resource_type": resource_type},
        )

        return handler.list_user_favorites(
            tenant_id=tenant_id, user_id=user_id, resource_type=resource_type, use_cache=use_cache
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to list user favorites: %s", e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list user favorites")


@router.put(
    "/{resource_type}/{resource_id}",
    response_model=UserFavoriteResponse,
    summary="Add user favorite",
    description="Add a resource to user favorites",
)
@authenticate()
@check_permissions(entity="user_favorite", required_permissions=[UserPermissionEnum.IS_CREATOR])
async def add_user_favorite(
    request: Request,
    tenant_id: str,
    user_id: str,
    resource_type: str,
    resource_id: str,
    handler: UserFavoritesHandler = Depends(get_user_favorites_handler),
) -> UserFavoriteResponse:
    """
    Add a resource to user favorites.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        user_id: User ID from path
        resource_type: Type of resource (chat-agents, autonomous-agents, development-platforms, conversations)
        resource_id: ID of the resource to favorite
        handler: User favorites handler dependency

    Returns:
        Created user favorite
    """
    try:
        logger.info(
            "API: Add user favorite",
            extra={
                "tenant_id": tenant_id,
                "user_id": user_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
            },
        )

        return handler.add_user_favorite(
            tenant_id=tenant_id, user_id=user_id, resource_type=resource_type, resource_id=resource_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to add user favorite: %s", e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to add user favorite")


@router.delete(
    "/{resource_type}/{resource_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove user favorite",
    description="Remove a resource from user favorites",
)
@authenticate()
@check_permissions(entity="user_favorite", required_permissions=[UserPermissionEnum.IS_CREATOR])
async def remove_user_favorite(
    request: Request,
    tenant_id: str,
    user_id: str,
    resource_type: str,
    resource_id: str,
    handler: UserFavoritesHandler = Depends(get_user_favorites_handler),
) -> Response:
    """
    Remove a resource from user favorites.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        user_id: User ID from path
        resource_type: Type of resource (chat-agents, autonomous-agents, development-platforms, conversations)
        resource_id: ID of the resource to unfavorite
        handler: User favorites handler dependency

    Returns:
        No content (204)
    """
    try:
        logger.info(
            "API: Remove user favorite",
            extra={
                "tenant_id": tenant_id,
                "user_id": user_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
            },
        )

        handler.remove_user_favorite(
            tenant_id=tenant_id, user_id=user_id, resource_type=resource_type, resource_id=resource_id
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to remove user favorite: %s", e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to remove user favorite")
