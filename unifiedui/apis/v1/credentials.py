"""API routes for credential management."""

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response

from unifiedui.core.database.enums import (
    ListViewEnum,
    OrderDirectionEnum,
    PermissionActionEnum,
    TenantRolesEnum,
)
from unifiedui.core.middleware.apis.v1.auth import authenticate, check_permissions
from unifiedui.exc.credentials import CredentialNotFoundError
from unifiedui.handlers.audit_helper import AuditActionEnum, AuditResourceTypeEnum, record_audit
from unifiedui.handlers.credentials import CredentialHandler
from unifiedui.handlers.dependencies import get_credential_handler
from unifiedui.handlers.field_filter import filtered_response, parse_ids
from unifiedui.handlers.validators.credential_validator import CredentialValidationError
from unifiedui.logger import get_logger
from unifiedui.schema.requests.credentials import (
    CreateCredentialRequest,
    TestCredentialConnectionRequest,
    UpdateCredentialRequest,
)
from unifiedui.schema.requests.permissions import SetResourcePermissionRequest
from unifiedui.schema.responses.credentials import (
    CredentialResponse,
    CredentialSecretResponse,
    TestCredentialConnectionResponse,
)
from unifiedui.schema.responses.principals import PrincipalWithRolesResponse, ResourcePrincipalsResponse

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser

logger = get_logger(__name__)

router = APIRouter(prefix="/credentials")


@router.get(
    "",
    summary="List credentials",
    description="Get a paginated list of credentials for the current tenant. Use view=quick-list to get only id and name.",
)
@authenticate()
async def list_credentials(
    request: Request,
    tenant_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return"),
    name: str | None = Query(None, description="Filter by credential name"),
    is_active: int | None = Query(None, ge=0, le=1, description="Filter by active status (1=active, 0=inactive)"),
    tags: str | None = Query(
        None, description="Comma-separated list of tag IDs to filter by (e.g., '10001,10002,10003')"
    ),
    order_by: str | None = Query(
        None, description="Column name to order by (e.g., 'name', 'created_at', 'updated_at')"
    ),
    order_direction: OrderDirectionEnum | None = Query(None, description="Sort direction: 'asc' or 'desc'"),
    view: ListViewEnum | None = Query(
        None, description="View type: 'full' (default) or 'quick-list' (returns only id and name)"
    ),
    ids: str | None = Query(None, description="Comma-separated list of IDs to filter by"),
    fields: str | None = Query(None, description="Comma-separated list of fields to include in the response"),
    handler: CredentialHandler = Depends(get_credential_handler),
):
    """
    List credentials for a tenant.

    Users see only credentials they have permissions for, unless they have
    TENANT_GLOBAL_ADMIN or CREDENTIALS_ADMIN on tenant level.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        skip: Number of items to skip
        limit: Maximum number of items to return
        name: Optional filter by credential name
        is_active: Optional filter by active status (None=all, 1=active, 0=inactive)
        tags: Optional comma-separated tag IDs to filter by
        handler: Credential handler dependency

    Returns:
        List of credentials (without secret values)
    """
    try:
        # Parse tag IDs from comma-separated string
        tag_ids = None
        if tags:
            try:
                tag_ids = [int(t.strip()) for t in tags.split(",") if t.strip()]
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid tag IDs format. Must be comma-separated integers.",
                )

        user: ContextIdentityUser = request.state.user

        logger.info(
            "API: List credentials",
            extra={"tenant_id": tenant_id, "user_id": user.identity.get_id(), "skip": skip, "limit": limit},
        )

        return filtered_response(
            handler.list_credentials(
                tenant_id=tenant_id,
                skip=skip,
                limit=limit,
                name_filter=name,
                is_active=is_active,
                user=user,
                tag_ids=tag_ids,
                order_by=order_by,
                order_direction=order_direction.value if order_direction else None,
                view=view.value if view else None,
                id_list=parse_ids(ids),
            ),
            fields,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list credentials: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list credentials")


@router.post(
    "",
    response_model=CredentialResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create credential",
    description="Create a new credential and store secret in vault",
)
@authenticate()
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CREDENTIALS_ADMIN,
        TenantRolesEnum.CREDENTIALS_CREATOR,
    ],
)
async def create_credential(
    request: Request,
    tenant_id: str,
    create_request: CreateCredentialRequest,
    handler: CredentialHandler = Depends(get_credential_handler),
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
            extra={"tenant_id": tenant_id, "user_id": user.identity.get_id(), "credential_name": create_request.name},
        )
        result = handler.create_credential(
            tenant_id=tenant_id, request=create_request, user_id=user.identity.get_id(), user=user
        )
        record_audit(
            request=request,
            tenant_id=tenant_id,
            action=AuditActionEnum.CREATE,
            resource_type=AuditResourceTypeEnum.CREDENTIAL,
            resource_id=str(result.id),
            resource_name=result.name,
        )
        return result
    except Exception as e:
        logger.error("Failed to create credential: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create credential")


@router.get(
    "/{credential_id}",
    response_model=CredentialResponse,
    summary="Get credential",
    description="Get a specific credential by ID (without secret value)",
)
@authenticate()
@check_permissions(entity="credential", required_permissions=[PermissionActionEnum.READ])
async def get_credential(
    request: Request,
    tenant_id: str,
    credential_id: str,
    fields: str | None = Query(None, description="Comma-separated list of fields to include in the response"),
    handler: CredentialHandler = Depends(get_credential_handler),
):
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
            extra={"tenant_id": tenant_id, "credential_id": credential_id, "user_id": user.identity.get_id()},
        )
        return filtered_response(
            handler.get_credential(tenant_id=tenant_id, credential_id=credential_id, user=user),
            fields,
        )
    except CredentialNotFoundError as e:
        logger.warning("Credential not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to get credential: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get credential")


@router.get(
    "/{credential_id}/secret",
    response_model=CredentialSecretResponse,
    summary="Get credential secret",
    description="Get the secret value of a credential from the vault",
)
@authenticate()
@check_permissions(
    entity="credential",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CREDENTIALS_ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.ADMIN,
    ],
)
async def get_credential_secret(
    request: Request, tenant_id: str, credential_id: str, handler: CredentialHandler = Depends(get_credential_handler)
) -> CredentialSecretResponse:
    """
    Get the secret value of a credential.

    This endpoint returns the actual secret value from the vault.
    Requires WRITE or ADMIN permission on the credential,
    or TENANT_GLOBAL_ADMIN/CREDENTIALS_ADMIN on the tenant.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        credential_id: Credential ID from path
        handler: Credential handler dependency

    Returns:
        The credential secret value

    Raises:
        HTTPException: If credential not found or access denied
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Get credential secret",
            extra={"tenant_id": tenant_id, "credential_id": credential_id, "user_id": user.identity.get_id()},
        )
        secret_value = handler.get_credential_secret(tenant_id=tenant_id, credential_id=credential_id)

        if secret_value is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Secret not found in vault")

        return CredentialSecretResponse(credential_id=credential_id, secret_value=secret_value)
    except CredentialNotFoundError as e:
        logger.warning("Credential not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get credential secret: %s", e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get credential secret")


@router.patch(
    "/{credential_id}",
    response_model=CredentialResponse,
    summary="Update credential",
    description="Update an existing credential and optionally update the secret",
)
@authenticate()
@check_permissions(entity="credential", required_permissions=[PermissionActionEnum.WRITE])
async def update_credential(
    request: Request,
    tenant_id: str,
    credential_id: str,
    update_request: UpdateCredentialRequest,
    handler: CredentialHandler = Depends(get_credential_handler),
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
            extra={"tenant_id": tenant_id, "credential_id": credential_id, "user_id": user.identity.get_id()},
        )
        result = handler.update_credential(
            tenant_id=tenant_id, credential_id=credential_id, request=update_request, user_id=user.identity.get_id()
        )
        record_audit(
            request=request,
            tenant_id=tenant_id,
            action=AuditActionEnum.UPDATE,
            resource_type=AuditResourceTypeEnum.CREDENTIAL,
            resource_id=str(credential_id),
            resource_name=getattr(result, "name", None),
            changes=update_request.model_dump(exclude_unset=True, mode="json", exclude={"secret_value"}),
        )
        return result
    except CredentialNotFoundError as e:
        logger.warning("Credential not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to update credential: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update credential")


@router.delete(
    "/{credential_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete credential",
    description="Delete a credential and its secret from the vault",
)
@authenticate()
@check_permissions(entity="credential", required_permissions=[PermissionActionEnum.ADMIN])
async def delete_credential(
    request: Request,
    tenant_id: str,
    credential_id: str,
    handler: CredentialHandler = Depends(get_credential_handler),
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
            extra={"tenant_id": tenant_id, "credential_id": credential_id, "user_id": user.identity.get_id()},
        )
        handler.delete_credential(tenant_id=tenant_id, credential_id=credential_id)
        record_audit(
            request=request,
            tenant_id=tenant_id,
            action=AuditActionEnum.DELETE,
            resource_type=AuditResourceTypeEnum.CREDENTIAL,
            resource_id=str(credential_id),
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except CredentialNotFoundError as e:
        logger.warning("Credential not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to delete credential: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete credential")


# ========== Credential Connection Test Endpoints ==========


@router.post(
    "/test-connection",
    response_model=TestCredentialConnectionResponse,
    summary="Test credential connection",
    description="Test a credential by attempting to acquire a token (ENTRA_ID_APP_REGISTRATION only)",
)
@authenticate()
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CREDENTIALS_ADMIN,
        TenantRolesEnum.CREDENTIALS_CREATOR,
    ],
)
async def test_credential_connection(
    request: Request,
    tenant_id: str,
    test_request: TestCredentialConnectionRequest,
    handler: CredentialHandler = Depends(get_credential_handler),
) -> TestCredentialConnectionResponse:
    """Test a credential connection by attempting to acquire a token.

    Currently supports ENTRA_ID_APP_REGISTRATION credentials only.
    Attempts to acquire an OAuth 2.0 token using the provided client credentials.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        test_request: Test connection request with credential details
        handler: Credential handler dependency

    Returns:
        Test connection result with success/failure and timing
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Test credential connection",
            extra={"tenant_id": tenant_id, "user_id": user.identity.get_id(), "type": test_request.credential_type},
        )
        return CredentialHandler.test_credential_connection(request=test_request)
    except CredentialValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except Exception as e:
        logger.error("Failed to test credential connection: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to test credential connection"
        )


# ========== Credential Permission Endpoints ==========


@router.get(
    "/{credential_id}/principals",
    response_model=ResourcePrincipalsResponse,
    summary="List credential permissions",
    description="Get all principals with permissions for a credential",
)
@authenticate()
@check_permissions(entity="credential", required_permissions=[PermissionActionEnum.READ])
async def list_credential_permissions(
    request: Request,
    tenant_id: str,
    credential_id: str,
    skip: int = Query(0, ge=0, description="Number of principals to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of principals to return"),
    search: str | None = Query(None, description="Search term for display_name, principal_name, or mail"),
    roles: str | None = Query(None, description="Comma-separated roles to filter by (OR logic)"),
    is_active: bool | None = Query(None, description="Filter by is_active status"),
    order_by: str | None = Query(None, enum=["display_name"], description="Column to order by"),
    order_direction: str | None = Query("asc", enum=["asc", "desc"], description="Sort direction"),
    handler: CredentialHandler = Depends(get_credential_handler),
) -> ResourcePrincipalsResponse:
    """
    List all permissions for a credential.

    Requires ADMIN permission on the credential or CREDENTIALS_ADMIN on tenant.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        credential_id: Credential ID from path
        skip: Number of principals to skip
        limit: Maximum number of principals to return
        search: Search term for display_name, principal_name, or mail
        roles: Comma-separated roles to filter by (OR logic)
        is_active: Filter by is_active status
        order_by: Column to order by
        order_direction: Sort direction
        handler: Credential handler dependency

    Returns:
        Grouped principals with their permissions
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: List credential permissions",
            extra={"tenant_id": tenant_id, "credential_id": credential_id, "user_id": user.identity.get_id()},
        )

        # Parse comma-separated roles
        roles_list = [r.strip() for r in roles.split(",")] if roles else None

        return handler.list_credential_permissions(
            tenant_id=tenant_id,
            credential_id=credential_id,
            skip=skip,
            limit=limit,
            search=search,
            roles=roles_list,
            is_active=is_active,
            order_by=order_by,
            order_direction=order_direction,
        )
    except CredentialNotFoundError as e:
        logger.warning("Credential not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to list credential permissions: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list credential permissions"
        )


@router.get(
    "/{credential_id}/principals/{principal_id}",
    response_model=PrincipalWithRolesResponse,
    summary="Get credential permissions for principal",
    description="Get all permissions for a specific principal on a credential",
)
@authenticate()
@check_permissions(entity="credential", required_permissions=[PermissionActionEnum.READ])
async def get_credential_permission(
    request: Request,
    tenant_id: str,
    credential_id: str,
    principal_id: str,
    handler: CredentialHandler = Depends(get_credential_handler),
) -> PrincipalWithRolesResponse:
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
                "user_id": user.identity.get_id(),
            },
        )
        return handler.get_credential_permission(
            tenant_id=tenant_id, credential_id=credential_id, principal_id=principal_id
        )
    except CredentialNotFoundError as e:
        logger.warning("Permission not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to get credential permission: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get credential permission"
        )


@router.put(
    "/{credential_id}/principals",
    response_model=PrincipalWithRolesResponse,
    summary="Set credential permission",
    description="Set or update a principal's permission for a credential",
)
@authenticate()
@check_permissions(entity="credential", required_permissions=[PermissionActionEnum.ADMIN])
async def set_credential_permission(
    request: Request,
    tenant_id: str,
    credential_id: str,
    permission_request: SetResourcePermissionRequest,
    handler: CredentialHandler = Depends(get_credential_handler),
) -> PrincipalWithRolesResponse:
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
                "user_id": user.identity.get_id(),
            },
        )
        result = handler.set_credential_permission(
            tenant_id=tenant_id,
            credential_id=credential_id,
            request=permission_request,
            user_id=user.identity.get_id(),
            user=user,
        )
        record_audit(
            request=request,
            tenant_id=tenant_id,
            action=AuditActionEnum.MEMBER_ADD,
            resource_type=AuditResourceTypeEnum.CREDENTIAL,
            resource_id=str(credential_id),
            changes={
                "principal_id": permission_request.principal_id,
                "role": str(getattr(permission_request, "role", None)),
            },
        )
        return result
    except CredentialNotFoundError as e:
        logger.warning("Credential not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to set credential permission: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to set credential permission"
        )


@router.delete(
    "/{credential_id}/principals",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete credential permission",
    description="Remove a principal's permission for a credential",
)
@authenticate()
@check_permissions(entity="credential", required_permissions=[PermissionActionEnum.ADMIN])
async def delete_credential_permission(
    request: Request,
    tenant_id: str,
    credential_id: str,
    delete_request: SetResourcePermissionRequest,
    handler: CredentialHandler = Depends(get_credential_handler),
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
                "user_id": user.identity.get_id(),
            },
        )
        handler.delete_credential_permission(
            tenant_id=tenant_id,
            credential_id=credential_id,
            principal_id=delete_request.principal_id,
            principal_type=delete_request.principal_type,
            permission=delete_request.role,  # Changed from .permission to .role
        )
        record_audit(
            request=request,
            tenant_id=tenant_id,
            action=AuditActionEnum.MEMBER_REMOVE,
            resource_type=AuditResourceTypeEnum.CREDENTIAL,
            resource_id=str(credential_id),
            changes={
                "principal_id": delete_request.principal_id,
                "role": str(getattr(delete_request, "role", None)),
            },
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except CredentialNotFoundError as e:
        logger.warning("Permission not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to delete credential permission: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete credential permission"
        )
