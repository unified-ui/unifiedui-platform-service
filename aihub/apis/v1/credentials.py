"""API routes for credential management."""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import Response

from aihub.core.identity.users import ContextIdentityUser
from aihub.handlers.credentials import CredentialHandler
from aihub.handlers.dependencies import get_credential_handler
from aihub.schema.requests.credentials import CreateCredentialRequest, UpdateCredentialRequest
from aihub.schema.requests.credential_permissions import SetCredentialPermissionRequest
from aihub.schema.responses.credentials import CredentialResponse
from aihub.schema.responses.credential_permissions import (
    CredentialPermissionResponse,
    CredentialPrincipalsResponse,
    PrincipalPermissionsResponse
)
from aihub.exc.credentials import CredentialNotFoundError
from aihub.core.middleware.apis.v1.auth import authenticate, check_permissions
from aihub.core.database.enums import TenantPermissionEnum, PermissionActionEnum
from aihub.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/credentials",
    tags=["credentials"]
)


@router.get(
    "",
    response_model=List[CredentialResponse],
    summary="List credentials",
    description="Get a paginated list of credentials for the current tenant"
)
@authenticate
async def list_credentials(
    request: Request,
    tenant_id: str,
    skip: int = 0,
    limit: int = 100,
    name_filter: Optional[str] = None,
    handler: CredentialHandler = Depends(get_credential_handler)
) -> List[CredentialResponse]:
    """
    List credentials for a tenant.
    
    Users see only credentials they have permissions for, unless they have
    GLOBAL_ADMIN or CREDENTIALS_ADMIN on tenant level.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        skip: Number of items to skip
        limit: Maximum number of items to return
        name_filter: Optional filter by credential name
        handler: Credential handler dependency
        
    Returns:
        List of credentials (without secret values)
    """
    try:
        user: ContextIdentityUser = request.state.user
        
        logger.info(
            "API: List credentials",
            extra={
                "tenant_id": tenant_id,
                "user_id": user.identity.get_id(),
                "skip": skip,
                "limit": limit
            }
        )
        
        return handler.list_credentials(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            name_filter=name_filter,
            user=user
        )
    except Exception as e:
        logger.error(f"Failed to list credentials: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list credentials"
        )


@router.post(
    "",
    response_model=CredentialResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create credential",
    description="Create a new credential and store secret in vault"
)
@authenticate
@check_permissions(entity="tenant", required_permissions=[TenantPermissionEnum.GLOBAL_ADMIN, TenantPermissionEnum.CREDENTIALS_ADMIN])
async def create_credential(
    request: Request,
    tenant_id: str,
    create_request: CreateCredentialRequest,
    handler: CredentialHandler = Depends(get_credential_handler)
) -> CredentialResponse:
    """
    Create a new credential.
    
    The secret value will be stored securely in the configured vault.
    Only the vault URI will be stored in the database.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        create_request: Credential creation data
        handler: Credential handler dependency
        
    Returns:
        Created credential (without secret value)
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Create credential",
            extra={
                "tenant_id": tenant_id,
                "user_id": user.identity.get_id(),
                "credential_name": create_request.name
            }
        )
        return handler.create_credential(
            tenant_id=tenant_id,
            request=create_request,
            user_id=user.identity.get_id()
        )
    except Exception as e:
        logger.error(f"Failed to create credential: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create credential: {str(e)}"
        )


@router.get(
    "/{credential_id}",
    response_model=CredentialResponse,
    summary="Get credential",
    description="Get a specific credential by ID (without secret value)"
)
@authenticate
@check_permissions(entity="credential", required_permissions=[PermissionActionEnum.READ])
async def get_credential(
    request: Request,
    tenant_id: str,
    credential_id: str,
    handler: CredentialHandler = Depends(get_credential_handler)
) -> CredentialResponse:
    """
    Get a specific credential.
    
    Note: The secret value is NOT included in the response.
    Use the internal get_credential_secret method for application use.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        credential_id: Credential ID from path
        handler: Credential handler dependency
        
    Returns:
        Credential details (without secret value)
        
    Raises:
        HTTPException: If credential not found or access denied
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Get credential",
            extra={
                "tenant_id": tenant_id,
                "credential_id": credential_id,
                "user_id": user.identity.get_id()
            }
        )
        return handler.get_credential(
            tenant_id=tenant_id,
            credential_id=credential_id
        )
    except CredentialNotFoundError as e:
        logger.warning(f"Credential not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get credential: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get credential"
        )


@router.patch(
    "/{credential_id}",
    response_model=CredentialResponse,
    summary="Update credential",
    description="Update an existing credential and optionally update the secret"
)
@authenticate
@check_permissions(entity="credential", required_permissions=[PermissionActionEnum.WRITE, PermissionActionEnum.ADMIN])
async def update_credential(
    request: Request,
    tenant_id: str,
    credential_id: str,
    update_request: UpdateCredentialRequest,
    handler: CredentialHandler = Depends(get_credential_handler)
) -> CredentialResponse:
    """
    Update a credential.
    
    If secret_value is provided, the secret in the vault will be updated.
    Other fields are optional and only updated if provided.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        credential_id: Credential ID from path
        update_request: Credential update data
        handler: Credential handler dependency
        
    Returns:
        Updated credential (without secret value)
        
    Raises:
        HTTPException: If credential not found or update fails
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Update credential",
            extra={
                "tenant_id": tenant_id,
                "credential_id": credential_id,
                "user_id": user.identity.get_id()
            }
        )
        return handler.update_credential(
            tenant_id=tenant_id,
            credential_id=credential_id,
            request=update_request,
            user_id=user.identity.get_id()
        )
    except CredentialNotFoundError as e:
        logger.warning(f"Credential not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update credential: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update credential: {str(e)}"
        )


@router.delete(
    "/{credential_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete credential",
    description="Delete a credential and its secret from the vault"
)
@authenticate
@check_permissions(entity="credential", required_permissions=[PermissionActionEnum.ADMIN])
async def delete_credential(
    request: Request,
    tenant_id: str,
    credential_id: str,
    handler: CredentialHandler = Depends(get_credential_handler)
) -> Response:
    """
    Delete a credential.
    
    This will remove both the credential metadata from the database
    and the secret from the vault.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        credential_id: Credential ID from path
        handler: Credential handler dependency
        
    Returns:
        No content (204)
        
    Raises:
        HTTPException: If credential not found or deletion fails
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Delete credential",
            extra={
                "tenant_id": tenant_id,
                "credential_id": credential_id,
                "user_id": user.identity.get_id()
            }
        )
        handler.delete_credential(
            tenant_id=tenant_id,
            credential_id=credential_id
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except CredentialNotFoundError as e:
        logger.warning(f"Credential not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete credential: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete credential"
        )


# ========== Credential Permission Endpoints ==========

@router.get(
    "/{credential_id}/principals",
    response_model=CredentialPrincipalsResponse,
    summary="List credential permissions",
    description="Get all principals with permissions for a credential"
)
@authenticate
@check_permissions(entity="credential", required_permissions=[PermissionActionEnum.ADMIN])
async def list_credential_permissions(
    request: Request,
    tenant_id: str,
    credential_id: str,
    handler: CredentialHandler = Depends(get_credential_handler)
) -> CredentialPrincipalsResponse:
    """
    List all permissions for a credential.
    
    Requires ADMIN permission on the credential or CREDENTIALS_ADMIN on tenant.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        credential_id: Credential ID from path
        handler: Credential handler dependency
        
    Returns:
        Grouped principals with their permissions
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: List credential permissions",
            extra={
                "tenant_id": tenant_id,
                "credential_id": credential_id,
                "user_id": user.identity.get_id()
            }
        )
        return handler.list_credential_permissions(
            tenant_id=tenant_id,
            credential_id=credential_id
        )
    except CredentialNotFoundError as e:
        logger.warning(f"Credential not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to list credential permissions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list credential permissions"
        )


@router.get(
    "/{credential_id}/principals/{principal_id}",
    response_model=PrincipalPermissionsResponse,
    summary="Get credential permissions for principal",
    description="Get all permissions for a specific principal on a credential"
)
@authenticate
@check_permissions(entity="credential", required_permissions=[PermissionActionEnum.ADMIN])
async def get_credential_permission(
    request: Request,
    tenant_id: str,
    credential_id: str,
    principal_id: str,
    handler: CredentialHandler = Depends(get_credential_handler)
) -> PrincipalPermissionsResponse:
    """
    Get all permissions for a specific principal on a credential.
    
    Requires ADMIN permission on the credential or CREDENTIALS_ADMIN on tenant.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        credential_id: Credential ID from path
        principal_id: Principal ID from path
        handler: Credential handler dependency
        
    Returns:
        Principal with all their permissions
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Get credential permission",
            extra={
                "tenant_id": tenant_id,
                "credential_id": credential_id,
                "principal_id": principal_id,
                "user_id": user.identity.get_id()
            }
        )
        return handler.get_credential_permission(
            tenant_id=tenant_id,
            credential_id=credential_id,
            principal_id=principal_id
        )
    except CredentialNotFoundError as e:
        logger.warning(f"Permission not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get credential permission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get credential permission"
        )


@router.put(
    "/{credential_id}/principals",
    response_model=CredentialPermissionResponse,
    summary="Set credential permission",
    description="Set or update a principal's permission for a credential"
)
@authenticate
@check_permissions(entity="credential", required_permissions=[PermissionActionEnum.ADMIN])
async def set_credential_permission(
    request: Request,
    tenant_id: str,
    credential_id: str,
    permission_request: SetCredentialPermissionRequest,
    handler: CredentialHandler = Depends(get_credential_handler)
) -> CredentialPermissionResponse:
    """
    Set or update a credential permission.
    
    Requires ADMIN permission on the credential or CREDENTIALS_ADMIN on tenant.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        credential_id: Credential ID from path
        permission_request: Permission data
        handler: Credential handler dependency
        
    Returns:
        Created or updated permission
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Set credential permission",
            extra={
                "tenant_id": tenant_id,
                "credential_id": credential_id,
                "principal_id": permission_request.principal_id,
                "user_id": user.identity.get_id()
            }
        )
        return handler.set_credential_permission(
            tenant_id=tenant_id,
            credential_id=credential_id,
            request=permission_request
        )
    except CredentialNotFoundError as e:
        logger.warning(f"Credential not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to set credential permission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set credential permission: {str(e)}"
        )


@router.delete(
    "/{credential_id}/principals",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete credential permission",
    description="Remove a principal's permission for a credential"
)
@authenticate
@check_permissions(entity="credential", required_permissions=[PermissionActionEnum.ADMIN])
async def delete_credential_permission(
    request: Request,
    tenant_id: str,
    credential_id: str,
    delete_request: SetCredentialPermissionRequest,
    handler: CredentialHandler = Depends(get_credential_handler)
) -> Response:
    """
    Delete a credential permission.
    
    Requires ADMIN permission on the credential or CREDENTIALS_ADMIN on tenant.
    
    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        credential_id: Credential ID from path
        delete_request: Permission deletion data (principal_id, principal_type, permission)
        handler: Credential handler dependency
        
    Returns:
        No content (204)
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Delete credential permission",
            extra={
                "tenant_id": tenant_id,
                "credential_id": credential_id,
                "principal_id": delete_request.principal_id,
                "user_id": user.identity.get_id()
            }
        )
        handler.delete_credential_permission(
            tenant_id=tenant_id,
            credential_id=credential_id,
            principal_id=delete_request.principal_id,
            principal_type=delete_request.principal_type,
            permission=delete_request.permission
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except CredentialNotFoundError as e:
        logger.warning(f"Permission not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete credential permission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete credential permission"
        )
