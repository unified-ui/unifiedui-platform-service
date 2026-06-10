"""API routes for tenant AI model management."""

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response

from unifiedui.core.database.enums import OrderDirectionEnum, TenantRolesEnum
from unifiedui.core.middleware.apis.v1.auth import authenticate, authenticate_service_key, check_permissions
from unifiedui.exc.tenant_ai_models import (
    InvalidAIModelCredentialError,
    TenantAIModelConfigValidationError,
    TenantAIModelNotFoundError,
    UnsupportedAIModelProviderError,
)
from unifiedui.handlers.dependencies.tenant_ai_models import get_tenant_ai_model_handler
from unifiedui.handlers.field_filter import filtered_response, parse_ids
from unifiedui.handlers.tenant_ai_models import TenantAIModelHandler
from unifiedui.logger import get_logger
from unifiedui.schema.requests.tenant_ai_models import (
    CreateTenantAIModelRequest,
    UpdateTenantAIModelRequest,
)
from unifiedui.schema.responses.tenant_ai_models import (
    TenantAIModelResponse,
)

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser

logger = get_logger(__name__)

router = APIRouter(prefix="/ai-models")


@router.get(
    "", summary="List tenant AI models", description="Get a list of AI models configured for the current tenant."
)
@authenticate()
async def list_tenant_ai_models(
    request: Request,
    tenant_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return"),
    name: str | None = Query(None, description="Filter by model name"),
    type: str | None = Query(
        None, description="Comma-separated list of model types to filter by (e.g., 'LLM_MODEL,EMBEDDING_MODEL')"
    ),
    provider: str | None = Query(
        None, description="Comma-separated list of providers to filter by (e.g., 'OPENAI,AZURE_OPENAI')"
    ),
    tags: str | None = Query(None, description="Comma-separated list of tag IDs to filter by (OR logic)"),
    order_by: str | None = Query(None, description="Column name to order by"),
    order_direction: OrderDirectionEnum | None = Query(None, description="Sort direction: 'asc' or 'desc'"),
    ids: str | None = Query(None, description="Comma-separated list of IDs to filter by"),
    fields: str | None = Query(None, description="Comma-separated list of fields to include in the response"),
    handler: TenantAIModelHandler = Depends(get_tenant_ai_model_handler),
):
    """List AI models for a tenant."""
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: List tenant AI models",
            extra={
                "tenant_id": tenant_id,
                "user_id": user.identity.get_id(),
                "skip": skip,
                "limit": limit,
            },
        )

        types = None
        if type:
            types = [t.strip() for t in type.split(",") if t.strip()]

        providers = None
        if provider:
            providers = [p.strip() for p in provider.split(",") if p.strip()]

        tag_ids = [int(t.strip()) for t in tags.split(",") if t.strip()] if tags else None

        return filtered_response(
            handler.list_tenant_ai_models(
                tenant_id=tenant_id,
                skip=skip,
                limit=limit,
                name_filter=name,
                type_filter=types,
                provider_filter=providers,
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
        logger.error("Failed to list tenant AI models: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list tenant AI models")


@router.post(
    "",
    response_model=TenantAIModelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create tenant AI model",
    description="Create a new AI model configuration for the tenant.",
)
@authenticate()
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.TENANT_AI_MODELS_ADMIN,
    ],
)
async def create_tenant_ai_model(
    request: Request,
    tenant_id: str,
    create_request: CreateTenantAIModelRequest,
    handler: TenantAIModelHandler = Depends(get_tenant_ai_model_handler),
) -> TenantAIModelResponse:
    """Create a new tenant AI model."""
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Create tenant AI model",
            extra={
                "tenant_id": tenant_id,
                "user_id": user.identity.get_id(),
                "model_name": create_request.name,
            },
        )
        return handler.create_tenant_ai_model(
            tenant_id=tenant_id,
            request=create_request,
            user_id=user.identity.get_id(),
        )
    except InvalidAIModelCredentialError as e:
        logger.warning("Invalid credential: %s", e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except TenantAIModelConfigValidationError as e:
        logger.warning("Config validation error: %s", e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except UnsupportedAIModelProviderError as e:
        logger.warning("Unsupported provider: %s", e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create tenant AI model: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create tenant AI model"
        )


@router.get(
    "/{model_id}",
    response_model=TenantAIModelResponse,
    summary="Get tenant AI model",
    description="Get a specific AI model by ID.",
)
@authenticate()
async def get_tenant_ai_model(
    request: Request,
    tenant_id: str,
    model_id: str,
    fields: str | None = Query(None, description="Comma-separated list of fields to include in the response"),
    handler: TenantAIModelHandler = Depends(get_tenant_ai_model_handler),
):
    """Get a specific tenant AI model."""
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Get tenant AI model",
            extra={
                "tenant_id": tenant_id,
                "model_id": model_id,
                "user_id": user.identity.get_id(),
            },
        )
        return filtered_response(
            handler.get_tenant_ai_model(
                tenant_id=tenant_id,
                model_id=model_id,
            ),
            fields,
        )
    except TenantAIModelNotFoundError as e:
        logger.warning("AI model not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get tenant AI model: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get tenant AI model")


@router.patch(
    "/{model_id}",
    response_model=TenantAIModelResponse,
    summary="Update tenant AI model",
    description="Update an existing AI model configuration.",
)
@authenticate()
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.TENANT_AI_MODELS_ADMIN,
    ],
)
async def update_tenant_ai_model(
    request: Request,
    tenant_id: str,
    model_id: str,
    update_request: UpdateTenantAIModelRequest,
    handler: TenantAIModelHandler = Depends(get_tenant_ai_model_handler),
) -> TenantAIModelResponse:
    """Update a tenant AI model."""
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Update tenant AI model",
            extra={
                "tenant_id": tenant_id,
                "model_id": model_id,
                "user_id": user.identity.get_id(),
            },
        )
        return handler.update_tenant_ai_model(
            tenant_id=tenant_id,
            model_id=model_id,
            request=update_request,
            user_id=user.identity.get_id(),
        )
    except TenantAIModelNotFoundError as e:
        logger.warning("AI model not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidAIModelCredentialError as e:
        logger.warning("Invalid credential: %s", e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except TenantAIModelConfigValidationError as e:
        logger.warning("Config validation error: %s", e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update tenant AI model: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update tenant AI model"
        )


@router.delete(
    "/{model_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete tenant AI model",
    description="Delete an AI model configuration.",
)
@authenticate()
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.TENANT_AI_MODELS_ADMIN,
    ],
)
async def delete_tenant_ai_model(
    request: Request,
    tenant_id: str,
    model_id: str,
    handler: TenantAIModelHandler = Depends(get_tenant_ai_model_handler),
) -> Response:
    """Delete a tenant AI model."""
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Delete tenant AI model",
            extra={
                "tenant_id": tenant_id,
                "model_id": model_id,
                "user_id": user.identity.get_id(),
            },
        )
        handler.delete_tenant_ai_model(
            tenant_id=tenant_id,
            model_id=model_id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except TenantAIModelNotFoundError as e:
        logger.warning("AI model not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete tenant AI model: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete tenant AI model"
        )


@router.get(
    "/by-purpose/{purpose_group}",
    summary="Get AI models by purpose group (S2S)",
    description="Get active AI models for a specific purpose group with decrypted credentials. Service-to-service only.",
)
@authenticate_service_key("X_AGENT_SERVICE_KEY")
async def get_models_by_purpose(
    request: Request,
    tenant_id: str,
    purpose_group: str,
    model_type: str | None = Query(None, description="Filter by model type"),
    handler: TenantAIModelHandler = Depends(get_tenant_ai_model_handler),
):
    """Get AI models by purpose group for service-to-service calls."""
    try:
        logger.info(
            "API: Get AI models by purpose (S2S)",
            extra={
                "tenant_id": tenant_id,
                "purpose_group": purpose_group,
                "model_type": model_type,
            },
        )
        return handler.get_models_by_purpose(
            tenant_id=tenant_id,
            purpose_group=purpose_group,
            model_type=model_type,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get AI models by purpose: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get AI models by purpose"
        )


@router.get(
    "/{model_id}/with-secret",
    summary="Get AI model by ID with secret (S2S)",
    description="Get a single active AI model with decrypted credentials. Service-to-service only.",
)
@authenticate_service_key("X_AGENT_SERVICE_KEY")
async def get_model_by_id_with_secret(
    request: Request,
    tenant_id: str,
    model_id: str,
    handler: TenantAIModelHandler = Depends(get_tenant_ai_model_handler),
):
    """Get a single AI model with decrypted credentials for service-to-service calls."""
    try:
        logger.info(
            "API: Get AI model by ID with secret (S2S)",
            extra={
                "tenant_id": tenant_id,
                "model_id": model_id,
            },
        )
        return handler.get_model_by_id_with_secret(
            tenant_id=tenant_id,
            model_id=model_id,
        )
    except TenantAIModelNotFoundError as e:
        logger.warning("AI model not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get AI model by ID with secret: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get AI model with secret"
        )
