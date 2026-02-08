"""API routes for tenant AI model management."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.responses import Response

from unifiedui.core.identity.users import ContextIdentityUser
from unifiedui.handlers.tenant_ai_models import TenantAIModelHandler
from unifiedui.handlers.dependencies.tenant_ai_models import get_tenant_ai_model_handler
from unifiedui.schema.requests.tenant_ai_models import (
    CreateTenantAIModelRequest,
    UpdateTenantAIModelRequest,
)
from unifiedui.schema.responses.tenant_ai_models import (
    TenantAIModelResponse,
    AIModelWithSecretResponse,
)
from unifiedui.exc.tenant_ai_models import (
    TenantAIModelNotFoundError,
    TenantAIModelConfigValidationError,
    UnsupportedAIModelProviderError,
    InvalidAIModelCredentialError,
)
from unifiedui.core.middleware.apis.v1.auth import authenticate, authenticate_service_key, check_permissions
from unifiedui.core.database.enums import TenantRolesEnum, OrderDirectionEnum
from unifiedui.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/ai-models"
)


@router.get(
    "",
    summary="List tenant AI models",
    description="Get a list of AI models configured for the current tenant."
)
@authenticate()
async def list_tenant_ai_models(
    request: Request,
    tenant_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return"),
    name: Optional[str] = Query(None, description="Filter by model name"),
    type: Optional[str] = Query(None, description="Comma-separated list of model types to filter by (e.g., 'LLM_MODEL,EMBEDDING_MODEL')"),
    provider: Optional[str] = Query(None, description="Comma-separated list of providers to filter by (e.g., 'OPENAI,AZURE_OPENAI')"),
    is_active: Optional[int] = Query(None, ge=0, le=1, description="Filter by active status (1=active, 0=inactive)"),
    order_by: Optional[str] = Query(None, description="Column name to order by"),
    order_direction: Optional[OrderDirectionEnum] = Query(None, description="Sort direction: 'asc' or 'desc'"),
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
            }
        )

        types = None
        if type:
            types = [t.strip() for t in type.split(",") if t.strip()]

        providers = None
        if provider:
            providers = [p.strip() for p in provider.split(",") if p.strip()]

        return handler.list_tenant_ai_models(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            name_filter=name,
            type_filter=types,
            provider_filter=providers,
            is_active=is_active,
            order_by=order_by,
            order_direction=order_direction.value if order_direction else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list tenant AI models: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list tenant AI models"
        )


@router.post(
    "",
    response_model=TenantAIModelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create tenant AI model",
    description="Create a new AI model configuration for the tenant."
)
@authenticate()
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.TENANT_AI_MODELS_ADMIN,
    ]
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
            }
        )
        return handler.create_tenant_ai_model(
            tenant_id=tenant_id,
            request=create_request,
            user_id=user.identity.get_id(),
        )
    except InvalidAIModelCredentialError as e:
        logger.warning(f"Invalid credential: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except TenantAIModelConfigValidationError as e:
        logger.warning(f"Config validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )
    except UnsupportedAIModelProviderError as e:
        logger.warning(f"Unsupported provider: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create tenant AI model: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create tenant AI model: {str(e)}"
        )


@router.get(
    "/{model_id}",
    response_model=TenantAIModelResponse,
    summary="Get tenant AI model",
    description="Get a specific AI model by ID."
)
@authenticate()
async def get_tenant_ai_model(
    request: Request,
    tenant_id: str,
    model_id: str,
    handler: TenantAIModelHandler = Depends(get_tenant_ai_model_handler),
) -> TenantAIModelResponse:
    """Get a specific tenant AI model."""
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Get tenant AI model",
            extra={
                "tenant_id": tenant_id,
                "model_id": model_id,
                "user_id": user.identity.get_id(),
            }
        )
        return handler.get_tenant_ai_model(
            tenant_id=tenant_id,
            model_id=model_id,
        )
    except TenantAIModelNotFoundError as e:
        logger.warning(f"AI model not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tenant AI model: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get tenant AI model"
        )


@router.patch(
    "/{model_id}",
    response_model=TenantAIModelResponse,
    summary="Update tenant AI model",
    description="Update an existing AI model configuration."
)
@authenticate()
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.TENANT_AI_MODELS_ADMIN,
    ]
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
            }
        )
        return handler.update_tenant_ai_model(
            tenant_id=tenant_id,
            model_id=model_id,
            request=update_request,
            user_id=user.identity.get_id(),
        )
    except TenantAIModelNotFoundError as e:
        logger.warning(f"AI model not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except InvalidAIModelCredentialError as e:
        logger.warning(f"Invalid credential: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except TenantAIModelConfigValidationError as e:
        logger.warning(f"Config validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update tenant AI model: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update tenant AI model: {str(e)}"
        )


@router.delete(
    "/{model_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete tenant AI model",
    description="Delete an AI model configuration."
)
@authenticate()
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantRolesEnum.GLOBAL_ADMIN,
        TenantRolesEnum.TENANT_AI_MODELS_ADMIN,
    ]
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
            }
        )
        handler.delete_tenant_ai_model(
            tenant_id=tenant_id,
            model_id=model_id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except TenantAIModelNotFoundError as e:
        logger.warning(f"AI model not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete tenant AI model: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete tenant AI model"
        )


@router.get(
    "/by-purpose/{purpose_group}",
    summary="Get AI models by purpose group (S2S)",
    description="Get active AI models for a specific purpose group with decrypted credentials. Service-to-service only."
)
@authenticate_service_key("X_AGENT_SERVICE_KEY")
async def get_models_by_purpose(
    request: Request,
    tenant_id: str,
    purpose_group: str,
    model_type: Optional[str] = Query(None, description="Filter by model type"),
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
            }
        )
        return handler.get_models_by_purpose(
            tenant_id=tenant_id,
            purpose_group=purpose_group,
            model_type=model_type,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get AI models by purpose: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get AI models by purpose"
        )
