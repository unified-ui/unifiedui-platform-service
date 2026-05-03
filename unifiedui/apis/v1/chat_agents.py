"""API routes for chat agent management."""

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response

from unifiedui.core.database.enums import (
    ChatAgentTypeEnum,
    ListViewEnum,
    OrderDirectionEnum,
    PermissionActionEnum,
    TenantRolesEnum,
)
from unifiedui.core.middleware.apis.v1.auth import authenticate, check_permissions
from unifiedui.exc.chat_agent_config import InvalidCredentialError
from unifiedui.exc.chat_agents import ChatAgentNotFoundError
from unifiedui.exc.re_act_agents import ReActAgentVersionNotFoundError
from unifiedui.handlers.audit_helper import AuditActionEnum, AuditResourceTypeEnum, record_audit
from unifiedui.handlers.chat_agents import ChatAgentHandler
from unifiedui.handlers.credentials import CredentialHandler
from unifiedui.handlers.dependencies import get_chat_agent_handler, get_credential_handler
from unifiedui.handlers.dependencies.foundry_connection import get_foundry_connection_tester
from unifiedui.handlers.field_filter import filtered_response, parse_ids
from unifiedui.handlers.foundry_connection import FoundryConnectionTester
from unifiedui.logger import get_logger
from unifiedui.schema.requests.chat_agents import (
    CreateChatAgentRequest,
    UpdateChatAgentRequest,
    UpdateReActAgentVersionRequest,
)
from unifiedui.schema.requests.permissions import SetResourcePermissionRequest
from unifiedui.schema.responses.chat_agents import ChatAgentConfigResponse, ChatAgentResponse
from unifiedui.schema.responses.principals import PrincipalWithRolesResponse, ResourcePrincipalsResponse
from unifiedui.schema.responses.re_act_agents import ReActAgentVersionResponse
from unifiedui.schema.test_connection import TestConnectionRequest, TestConnectionResponse

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser

logger = get_logger(__name__)

router = APIRouter(prefix="/chat-agents")


@router.post(
    "/test-connection",
    response_model=TestConnectionResponse,
    summary="Test chat-agent connection",
    description=(
        "Probe a Foundry chat agent for reachability and authentication. "
        "Works for unsaved configs (create/edit dialog)."
    ),
)
@authenticate()
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_AGENTS_ADMIN,
        TenantRolesEnum.CHAT_AGENTS_CREATOR,
    ],
)
async def test_chat_agent_connection(
    request: Request,
    tenant_id: str,
    payload: TestConnectionRequest,
    tester: FoundryConnectionTester = Depends(get_foundry_connection_tester),
) -> TestConnectionResponse:
    """Test connection to a Foundry chat agent without persisting it.

    Args:
        request: FastAPI request providing the user identity and bearer token.
        tenant_id: Tenant scope used for credential lookup.
        payload: Foundry config to probe.
        tester: Foundry connection tester dependency.

    Returns:
        TestConnectionResponse with success/error/latency metadata.
    """
    user: ContextIdentityUser = request.state.user
    user_token = getattr(user, "raw_token", None) or getattr(user.identity, "raw_token", None)
    logger.info(
        "API: Test chat-agent connection",
        extra={
            "tenant_id": tenant_id,
            "user_id": user.identity.get_id(),
            "auth_type": payload.auth_type,
            "agent_name": payload.agent_name,
        },
    )
    return tester.test(tenant_id=tenant_id, request=payload, user_token=user_token)


@router.get(
    "",
    summary="List chat agents",
    description="Get a paginated list of chat agents for the current tenant. Use view=quick-list to get only id and name.",
)
@authenticate()
async def list_chat_agents(
    request: Request,
    tenant_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return"),
    name: str | None = Query(None, description="Filter by chat agent name"),
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
    type: ChatAgentTypeEnum | None = Query(None, description="Filter by chat agent type (e.g., 'REACT_AGENT', 'N8N')"),
    ids: str | None = Query(None, description="Comma-separated list of IDs to filter by"),
    fields: str | None = Query(None, description="Comma-separated list of fields to include in the response"),
    handler: ChatAgentHandler = Depends(get_chat_agent_handler),
):
    """
    List chat agents for a tenant.

    Users see only chat agents they have permissions for, unless they have
    TENANT_GLOBAL_ADMIN or CHAT_AGENTS_ADMIN on tenant level.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        skip: Number of items to skip
        limit: Maximum number of items to return
        name: Optional filter by chat agent name
        is_active: Optional filter by active status (None=all, 1=active, 0=inactive)
        tags: Optional comma-separated tag IDs to filter by
        handler: Chat agent handler dependency

    Returns:
        List of chat agents
    """
    try:
        user: ContextIdentityUser = request.state.user

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

        logger.info(
            "API: List chat agents",
            extra={
                "tenant_id": tenant_id,
                "user_id": user.identity.get_id(),
                "skip": skip,
                "limit": limit,
                "tags": tag_ids,
            },
        )

        return filtered_response(
            handler.list_chat_agents(
                tenant_id=tenant_id,
                skip=skip,
                limit=limit,
                name_filter=name,
                is_active=is_active,
                tag_ids=tag_ids,
                order_by=order_by,
                order_direction=order_direction.value if order_direction else None,
                view=view.value if view else None,
                type_filter=type.value if type else None,
                user=user,
                id_list=parse_ids(ids),
            ),
            fields,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list chat agents: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list chat agents")


@router.post(
    "",
    response_model=ChatAgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create chat agent",
    description="Create a new chat agent",
)
@authenticate()
@check_permissions(
    entity="tenant",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_AGENTS_ADMIN,
        TenantRolesEnum.CHAT_AGENTS_CREATOR,
    ],
)
async def create_chat_agent(
    request: Request,
    tenant_id: str,
    create_request: CreateChatAgentRequest,
    handler: ChatAgentHandler = Depends(get_chat_agent_handler),
) -> ChatAgentResponse:
    """
    Create a new chat agent.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        create_request: Chat agent creation data
        handler: Chat agent handler dependency

    Returns:
        Created chat agent
    """
    user: ContextIdentityUser = request.state.user
    logger.info(
        "API: Create chat agent",
        extra={"tenant_id": tenant_id, "user_id": user.identity.get_id(), "app_name": create_request.name},
    )
    result = handler.create_chat_agent(
        tenant_id=tenant_id, request=create_request, user_id=user.identity.get_id(), user=user
    )
    record_audit(
        request=request,
        tenant_id=tenant_id,
        action=AuditActionEnum.CREATE,
        resource_type=AuditResourceTypeEnum.CHAT_AGENT,
        resource_id=str(result.id),
        resource_name=result.name,
    )
    return result


@router.get(
    "/{chat_agent_id}",
    response_model=ChatAgentResponse,
    summary="Get chat agent",
    description="Get a specific chat agent by ID",
)
@authenticate()
@check_permissions(
    entity="chat_agent",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ,
    ],
)
async def get_chat_agent(
    request: Request,
    tenant_id: str,
    chat_agent_id: str,
    fields: str | None = Query(None, description="Comma-separated list of fields to include in the response"),
    handler: ChatAgentHandler = Depends(get_chat_agent_handler),
):
    """
    Get a specific chat agent.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        chat_agent_id: Chat agent ID from path
        handler: Chat agent handler dependency

    Returns:
        Chat agent details

    Raises:
        HTTPException: If chat agent not found or access denied
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Get chat agent",
            extra={"tenant_id": tenant_id, "chat_agent_id": chat_agent_id, "user_id": user.identity.get_id()},
        )
        return filtered_response(
            handler.get_chat_agent(tenant_id=tenant_id, chat_agent_id=chat_agent_id, user=user),
            fields,
        )
    except ChatAgentNotFoundError as e:
        logger.warning("Chat agent not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to get chat agent: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get chat agent")


@router.patch(
    "/{chat_agent_id}",
    response_model=ChatAgentResponse,
    summary="Update chat agent",
    description="Update an existing chat agent",
)
@authenticate()
@check_permissions(
    entity="chat_agent",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def update_chat_agent(
    request: Request,
    tenant_id: str,
    chat_agent_id: str,
    update_request: UpdateChatAgentRequest,
    handler: ChatAgentHandler = Depends(get_chat_agent_handler),
) -> ChatAgentResponse:
    """
    Update a chat agent.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        chat_agent_id: Chat agent ID from path
        update_request: Chat agent update data
        handler: Chat agent handler dependency

    Returns:
        Updated chat agent
    """
    user: ContextIdentityUser = request.state.user
    logger.info(
        "API: Update chat agent",
        extra={"tenant_id": tenant_id, "chat_agent_id": chat_agent_id, "user_id": user.identity.get_id()},
    )
    result = handler.update_chat_agent(
        tenant_id=tenant_id, chat_agent_id=chat_agent_id, request=update_request, user_id=user.identity.get_id()
    )
    record_audit(
        request=request,
        tenant_id=tenant_id,
        action=AuditActionEnum.UPDATE,
        resource_type=AuditResourceTypeEnum.CHAT_AGENT,
        resource_id=str(chat_agent_id),
        resource_name=getattr(result, "name", None),
        changes=update_request.model_dump(exclude_unset=True, mode="json"),
    )
    return result


@router.delete(
    "/{chat_agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete chat agent",
    description="Delete a chat agent",
)
@authenticate()
@check_permissions(
    entity="chat_agent",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
    ],
)
async def delete_chat_agent(
    request: Request,
    tenant_id: str,
    chat_agent_id: str,
    handler: ChatAgentHandler = Depends(get_chat_agent_handler),
) -> Response:
    """
    Delete a chat agent.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        chat_agent_id: Chat agent ID from path
        handler: Chat agent handler dependency

    Returns:
        No content (204)

    Raises:
        HTTPException: If chat agent not found or deletion fails
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Delete chat agent",
            extra={"tenant_id": tenant_id, "chat_agent_id": chat_agent_id, "user_id": user.identity.get_id()},
        )
        handler.delete_chat_agent(tenant_id=tenant_id, chat_agent_id=chat_agent_id)
        record_audit(
            request=request,
            tenant_id=tenant_id,
            action=AuditActionEnum.DELETE,
            resource_type=AuditResourceTypeEnum.CHAT_AGENT,
            resource_id=str(chat_agent_id),
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ChatAgentNotFoundError as e:
        logger.warning("Chat agent not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to delete chat agent: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete chat agent")


@router.post(
    "/{chat_agent_id}/duplicate",
    response_model=ChatAgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Duplicate chat agent",
    description="Create an exact copy of a chat agent with name + ' Copy'",
)
@authenticate()
@check_permissions(
    entity="chat_agent",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_AGENTS_ADMIN,
        TenantRolesEnum.CHAT_AGENTS_CREATOR,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def duplicate_chat_agent(
    request: Request,
    tenant_id: str,
    chat_agent_id: str,
    handler: ChatAgentHandler = Depends(get_chat_agent_handler),
) -> ChatAgentResponse:
    """
    Duplicate a chat agent.

    Creates an exact copy of the chat agent with name + " Copy".
    Requires WRITE permission or higher on the chat agent, or CHAT_AGENTS_CREATOR on tenant.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        chat_agent_id: Chat agent ID to duplicate

    Returns:
        The newly created chat agent
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Duplicate chat agent",
            extra={"tenant_id": tenant_id, "chat_agent_id": chat_agent_id, "user_id": user.identity.get_id()},
        )
        result = handler.duplicate_chat_agent(
            tenant_id=tenant_id, chat_agent_id=chat_agent_id, user_id=user.identity.get_id(), user=user
        )
        record_audit(
            request=request,
            tenant_id=tenant_id,
            action=AuditActionEnum.CREATE,
            resource_type=AuditResourceTypeEnum.CHAT_AGENT,
            resource_id=str(result.id),
            resource_name=result.name,
            changes={"duplicated_from": str(chat_agent_id)},
        )
        return result
    except ChatAgentNotFoundError as e:
        logger.warning("Chat agent not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to duplicate chat agent: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to duplicate chat agent: {e!s}"
        )


# ========== Chat Agent Config Endpoint (for Agent Service) ==========


@router.get(
    "/{chat_agent_id}/config",
    response_model=ChatAgentConfigResponse,
    summary="Get chat agent config with credentials",
    description="Get the full chat agent configuration including credential secrets and user data. For internal agent-service use. Requires X-Service-Key header.",
)
@authenticate(required_service_auth_key="X_AGENT_SERVICE_KEY")
@check_permissions(
    entity="chat_agent",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ,
    ],
)
async def get_chat_agent_config(
    request: Request,
    tenant_id: str,
    chat_agent_id: str,
    handler: ChatAgentHandler = Depends(get_chat_agent_handler),
    credential_handler: CredentialHandler = Depends(get_credential_handler),
) -> ChatAgentConfigResponse:
    """
    Get the full chat agent configuration including credential secrets.

    This endpoint is intended for the agent-service to fetch complete
    configuration including resolved credential secrets and user information.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        chat_agent_id: Chat agent ID from path
        handler: Chat agent handler dependency
        credential_handler: Credential handler dependency

    Returns:
        ChatAgentConfigResponse with full config including secrets

    Raises:
        HTTPException: If chat agent not found, credentials invalid, or access denied
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Get chat agent config",
            extra={"tenant_id": tenant_id, "chat_agent_id": chat_agent_id, "user_id": user.identity.get_id()},
        )
        return handler.get_chat_agent_config(
            tenant_id=tenant_id, chat_agent_id=chat_agent_id, user=user, credential_handler=credential_handler
        )
    except ChatAgentNotFoundError as e:
        logger.warning("Chat agent not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidCredentialError as e:
        logger.error("Invalid credential: %s", e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e.message))
    except Exception as e:
        logger.error("Failed to get chat agent config: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get chat agent config: {e!s}"
        )


# ========== Chat Agent Version Endpoints (REACT_AGENT) ==========


@router.patch(
    "/{chat_agent_id}/versions",
    response_model=ChatAgentResponse,
    summary="Create new chat agent version",
    description="Create a new version of the chat agent config (REACT_AGENT only). Applies partial update to the latest version.",
)
@authenticate()
@check_permissions(
    entity="chat_agent",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_AGENTS_ADMIN,
        TenantRolesEnum.REACT_AGENT_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def update_chat_agent_version(
    request: Request,
    tenant_id: str,
    chat_agent_id: str,
    body: UpdateReActAgentVersionRequest,
    handler: ChatAgentHandler = Depends(get_chat_agent_handler),
) -> ChatAgentResponse:
    """Create a new version of a REACT_AGENT chat agent.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        chat_agent_id: Chat agent ID from path
        body: Version update data
        handler: Chat agent handler dependency

    Returns:
        Updated ChatAgentResponse

    Raises:
        HTTPException: If chat agent not found or update fails
    """
    try:
        user: ContextIdentityUser = request.state.user
        result = handler.update_chat_agent_version(
            tenant_id=tenant_id,
            chat_agent_id=chat_agent_id,
            request=body,
            user_id=user.identity.get_id(),
        )
        record_audit(
            request=request,
            tenant_id=tenant_id,
            action=AuditActionEnum.UPDATE,
            resource_type=AuditResourceTypeEnum.CHAT_AGENT,
            resource_id=str(chat_agent_id),
            resource_name=getattr(result, "name", None),
            changes={"version": "new"},
        )
        return result
    except ChatAgentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to update chat agent version: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update chat agent version"
        )


@router.get(
    "/{chat_agent_id}/versions",
    response_model=list[ReActAgentVersionResponse],
    summary="List chat agent versions",
    description="List all versions of a chat agent (REACT_AGENT only).",
)
@authenticate()
@check_permissions(
    entity="chat_agent",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_AGENTS_ADMIN,
        TenantRolesEnum.REACT_AGENT_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ,
    ],
)
async def list_chat_agent_versions(
    request: Request,
    tenant_id: str,
    chat_agent_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of items to return"),
    handler: ChatAgentHandler = Depends(get_chat_agent_handler),
) -> list[ReActAgentVersionResponse]:
    """List all versions of a chat agent.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        chat_agent_id: Chat agent ID from path
        skip: Number of items to skip
        limit: Maximum number of items to return
        handler: Chat agent handler dependency

    Returns:
        List of ReActAgentVersionResponse

    Raises:
        HTTPException: If chat agent not found
    """
    try:
        return handler.list_chat_agent_versions(
            tenant_id=tenant_id, chat_agent_id=chat_agent_id, skip=skip, limit=limit
        )
    except ChatAgentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to list chat agent versions: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list chat agent versions"
        )


@router.get(
    "/{chat_agent_id}/versions/{version}",
    response_model=ReActAgentVersionResponse,
    summary="Get chat agent version",
    description="Get a specific version of a chat agent (REACT_AGENT only).",
)
@authenticate()
@check_permissions(
    entity="chat_agent",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_AGENTS_ADMIN,
        TenantRolesEnum.REACT_AGENT_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ,
    ],
)
async def get_chat_agent_version(
    request: Request,
    tenant_id: str,
    chat_agent_id: str,
    version: int,
    handler: ChatAgentHandler = Depends(get_chat_agent_handler),
) -> ReActAgentVersionResponse:
    """Get a specific version of a chat agent.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        chat_agent_id: Chat agent ID from path
        version: Version number
        handler: Chat agent handler dependency

    Returns:
        ReActAgentVersionResponse

    Raises:
        HTTPException: If version not found
    """
    try:
        return handler.get_chat_agent_version(tenant_id=tenant_id, chat_agent_id=chat_agent_id, version=version)
    except (ChatAgentNotFoundError, ReActAgentVersionNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to get chat agent version: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get chat agent version"
        )


@router.post(
    "/{chat_agent_id}/versions/{version}/restore",
    response_model=ChatAgentResponse,
    summary="Restore chat agent version",
    description="Restore a previous version by creating a new version with the same config.",
)
@authenticate()
@check_permissions(
    entity="chat_agent",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_AGENTS_ADMIN,
        TenantRolesEnum.REACT_AGENT_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
    ],
)
async def restore_chat_agent_version(
    request: Request,
    tenant_id: str,
    chat_agent_id: str,
    version: int,
    handler: ChatAgentHandler = Depends(get_chat_agent_handler),
) -> ChatAgentResponse:
    """Restore a previous version of a chat agent.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        chat_agent_id: Chat agent ID from path
        version: Version number to restore
        handler: Chat agent handler dependency

    Returns:
        Updated ChatAgentResponse with restored version as latest

    Raises:
        HTTPException: If version not found
    """
    try:
        user: ContextIdentityUser = request.state.user
        result = handler.restore_chat_agent_version(
            tenant_id=tenant_id,
            chat_agent_id=chat_agent_id,
            version=version,
            user_id=user.identity.get_id(),
        )
        record_audit(
            request=request,
            tenant_id=tenant_id,
            action=AuditActionEnum.UPDATE,
            resource_type=AuditResourceTypeEnum.CHAT_AGENT,
            resource_id=str(chat_agent_id),
            resource_name=getattr(result, "name", None),
            changes={"restored_from_version": version},
        )
        return result
    except (ChatAgentNotFoundError, ReActAgentVersionNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to restore chat agent version: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to restore chat agent version"
        )


# ========== Chat Agent Permission Endpoints ==========


@router.get(
    "/{chat_agent_id}/principals",
    response_model=ResourcePrincipalsResponse,
    summary="List chat agent permissions",
    description="Get all principals with permissions for a chat agent",
)
@authenticate()
@check_permissions(
    entity="chat_agent",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ,
    ],
)
async def list_chat_agent_permissions(
    request: Request,
    tenant_id: str,
    chat_agent_id: str,
    skip: int = Query(0, ge=0, description="Number of principals to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of principals to return"),
    search: str | None = Query(None, description="Search term for display_name, principal_name, or mail"),
    roles: str | None = Query(None, description="Comma-separated roles to filter by (OR logic)"),
    is_active: bool | None = Query(None, description="Filter by is_active status"),
    order_by: str | None = Query(None, enum=["display_name"], description="Column to order by"),
    order_direction: str | None = Query("asc", enum=["asc", "desc"], description="Sort direction"),
    handler: ChatAgentHandler = Depends(get_chat_agent_handler),
) -> ResourcePrincipalsResponse:
    """
    List all permissions for a chat agent.

    Requires ADMIN permission on the chat agent or CHAT_AGENTS_ADMIN on tenant.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        chat_agent_id: Chat agent ID from path
        skip: Number of principals to skip
        limit: Maximum number of principals to return
        search: Search term for display_name, principal_name, or mail
        roles: Comma-separated roles to filter by (OR logic)
        is_active: Filter by is_active status
        order_by: Column to order by
        order_direction: Sort direction
        handler: Chat agent handler dependency

    Returns:
        Unified ResourcePrincipalsResponse with enriched principal data
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: List chat agent permissions",
            extra={"tenant_id": tenant_id, "chat_agent_id": chat_agent_id, "user_id": user.identity.get_id()},
        )

        # Parse comma-separated roles
        roles_list = [r.strip() for r in roles.split(",")] if roles else None

        return handler.list_chat_agent_permissions(
            tenant_id=tenant_id,
            chat_agent_id=chat_agent_id,
            skip=skip,
            limit=limit,
            search=search,
            roles=roles_list,
            is_active=is_active,
            order_by=order_by,
            order_direction=order_direction,
        )
    except ChatAgentNotFoundError as e:
        logger.warning("Chat agent not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to list chat agent permissions: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list chat agent permissions"
        )


@router.get(
    "/{chat_agent_id}/principals/{principal_id}",
    response_model=PrincipalWithRolesResponse,
    summary="Get chat agent permissions for principal",
    description="Get all permissions for a specific principal on a chat agent",
)
@authenticate()
@check_permissions(
    entity="chat_agent",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
        PermissionActionEnum.WRITE,
        PermissionActionEnum.READ,
    ],
)
async def get_chat_agent_permission(
    request: Request,
    tenant_id: str,
    chat_agent_id: str,
    principal_id: str,
    handler: ChatAgentHandler = Depends(get_chat_agent_handler),
) -> PrincipalWithRolesResponse:
    """
    Get all permissions for a specific principal on a chat agent.

    Requires ADMIN permission on the chat agent or CHAT_AGENTS_ADMIN on tenant.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        chat_agent_id: Chat agent ID from path
        principal_id: Principal ID from path
        handler: Chat agent handler dependency

    Returns:
        Unified PrincipalWithRolesResponse with enriched principal data
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Get chat agent permission",
            extra={
                "tenant_id": tenant_id,
                "chat_agent_id": chat_agent_id,
                "principal_id": principal_id,
                "user_id": user.identity.get_id(),
            },
        )
        return handler.get_chat_agent_permission(
            tenant_id=tenant_id, chat_agent_id=chat_agent_id, principal_id=principal_id
        )
    except ChatAgentNotFoundError as e:
        logger.warning("Permission not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to get chat agent permission: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get chat agent permission"
        )


@router.put(
    "/{chat_agent_id}/principals",
    response_model=PrincipalWithRolesResponse,
    summary="Set chat agent permission",
    description="Set or update a principal's permission for a chat agent",
)
@authenticate()
@check_permissions(
    entity="chat_agent",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
    ],
)
async def set_chat_agent_permission(
    request: Request,
    tenant_id: str,
    chat_agent_id: str,
    permission_request: SetResourcePermissionRequest,
    handler: ChatAgentHandler = Depends(get_chat_agent_handler),
) -> PrincipalWithRolesResponse:
    """
    Set or update a chat agent permission.

    Requires ADMIN permission on the chat agent or CHAT_AGENTS_ADMIN on tenant.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        chat_agent_id: Chat agent ID from path
        permission_request: Permission data
        handler: Chat agent handler dependency

    Returns:
        Updated principal with their roles and enriched data
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Set chat agent permission",
            extra={
                "tenant_id": tenant_id,
                "chat_agent_id": chat_agent_id,
                "principal_id": permission_request.principal_id,
                "user_id": user.identity.get_id(),
            },
        )
        result = handler.set_chat_agent_permission(
            tenant_id=tenant_id,
            chat_agent_id=chat_agent_id,
            request=permission_request,
            user_id=user.identity.get_id(),
            user=user,
        )
        record_audit(
            request=request,
            tenant_id=tenant_id,
            action=AuditActionEnum.MEMBER_ADD,
            resource_type=AuditResourceTypeEnum.CHAT_AGENT,
            resource_id=str(chat_agent_id),
            changes={
                "principal_id": permission_request.principal_id,
                "role": str(getattr(permission_request, "role", None)),
            },
        )
        return result
    except ChatAgentNotFoundError as e:
        logger.warning("Chat agent not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to set chat agent permission: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to set chat agent permission: {e!s}"
        )


@router.delete(
    "/{chat_agent_id}/principals",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete chat agent permission",
    description="Remove a principal's permission for a chat agent",
)
@authenticate()
@check_permissions(
    entity="chat_agent",
    required_permissions=[
        TenantRolesEnum.TENANT_GLOBAL_ADMIN,
        TenantRolesEnum.CHAT_AGENTS_ADMIN,
        PermissionActionEnum.ADMIN,
    ],
)
async def delete_chat_agent_permission(
    request: Request,
    tenant_id: str,
    chat_agent_id: str,
    delete_request: SetResourcePermissionRequest,
    handler: ChatAgentHandler = Depends(get_chat_agent_handler),
) -> Response:
    """
    Delete a chat agent permission.

    Requires ADMIN permission on the chat agent or CHAT_AGENTS_ADMIN on tenant.

    Args:
        request: FastAPI request with user in state
        tenant_id: Tenant ID from path
        chat_agent_id: Chat agent ID from path
        delete_request: Permission deletion data (principal_id, principal_type, permission)
        handler: Chat agent handler dependency

    Returns:
        No content (204)
    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Delete chat agent permission",
            extra={
                "tenant_id": tenant_id,
                "chat_agent_id": chat_agent_id,
                "principal_id": delete_request.principal_id,
                "user_id": user.identity.get_id(),
            },
        )
        handler.delete_chat_agent_permission(
            tenant_id=tenant_id,
            chat_agent_id=chat_agent_id,
            principal_id=delete_request.principal_id,
            principal_type=delete_request.principal_type.value,
            permission=delete_request.role.value,
        )
        record_audit(
            request=request,
            tenant_id=tenant_id,
            action=AuditActionEnum.MEMBER_REMOVE,
            resource_type=AuditResourceTypeEnum.CHAT_AGENT,
            resource_id=str(chat_agent_id),
            changes={
                "principal_id": delete_request.principal_id,
                "role": str(getattr(delete_request, "role", None)),
            },
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ChatAgentNotFoundError as e:
        logger.warning("Permission not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to delete chat agent permission: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete chat agent permission"
        )
