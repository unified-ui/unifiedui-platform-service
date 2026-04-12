from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from unifiedui.apis.v1 import (
    auth,
    chat_agents,
    chat_widgets,
    config_suggestions,
    conversations,
    credentials,
    custom_groups,
    dashboard,
    external_apps,
    files,
    foundry,
    health,
    identity,
    n8n,
    organizations,
    principals,
    recent_visits,
    search,
    tags,
    tenant_ai_models,
    tenants,
    tools,
    user_favorites,
    workflows,
)
from unifiedui.core.config import settings
from unifiedui.exc.auth import AuthError, InvalidCredentialsError, InvalidRefreshTokenError, LDAPConnectionError
from unifiedui.exc.chat_agent_config import (
    ChatAgentConfigValidationError,
    InvalidAIModelReferenceError,
    InvalidCredentialError,
    UnsupportedChatAgentTypeError,
)
from unifiedui.exc.chat_agents import ChatAgentNotFoundError
from unifiedui.exc.chat_widgets import ChatWidgetNotFoundError
from unifiedui.exc.conversations import ConversationNotFoundError
from unifiedui.exc.credentials import CredentialNotFoundError
from unifiedui.exc.custom_groups import CustomGroupError, CustomGroupNotFoundError
from unifiedui.exc.external_apps import ExternalAppAlreadyExistsError, ExternalAppNotFoundError
from unifiedui.exc.files import FileNotFoundByIdError, FileStorageNotConfiguredError, FileTooLargeError
from unifiedui.exc.organizations import (
    OrganizationAlreadyExistsError,
    OrganizationError,
    OrganizationMemberAlreadyExistsError,
    OrganizationMemberNotFoundError,
    OrganizationNameAlreadyExistsError,
    OrganizationNotFoundError,
    OrganizationSlugAlreadyExistsError,
    TenantCannotBeDeletedError,
)
from unifiedui.exc.permissions import PermissionDeniedError
from unifiedui.exc.principal import PrincipalNotFoundError
from unifiedui.exc.tags import TagDeleteNotAllowedError, TagNotFoundError
from unifiedui.exc.tenant_ai_models import (
    InvalidAIModelCredentialError,
    TenantAIModelConfigValidationError,
    TenantAIModelNotFoundError,
    UnsupportedAIModelProviderError,
)
from unifiedui.exc.tenants import TenantAlreadyExistsError, TenantError, TenantNotFoundError
from unifiedui.exc.tools import (
    InvalidToolCredentialError,
    ToolConfigValidationError,
    ToolNotFoundError,
    UnsupportedToolTypeError,
)
from unifiedui.exc.workflows import WorkflowNotFoundError
from unifiedui.handlers.validators.credential_validator import (
    CredentialValidationError,
    UnsupportedCredentialTypeError,
)
from unifiedui.logger import get_logger, setup_logging

# Configure logging
setup_logging()
logger = get_logger(__name__)

load_dotenv()


def create_app() -> FastAPI:
    """Create and configure FastAPI application following best practices."""

    app = FastAPI(
        title=settings.api_title,
        description=settings.api_description,
        version=settings.api_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    # Exception Handlers
    @app.exception_handler(PermissionDeniedError)
    async def permission_denied_handler(request: Request, exc: PermissionDeniedError):
        """Handle permission denied errors."""
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(TenantNotFoundError)
    async def tenant_not_found_handler(request: Request, exc: TenantNotFoundError):
        """Handle tenant not found errors."""
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(TenantAlreadyExistsError)
    async def tenant_already_exists_handler(request: Request, exc: TenantAlreadyExistsError):
        """Handle tenant already exists errors."""
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(TenantError)
    async def tenant_error_handler(request: Request, exc: TenantError):
        """Handle general tenant errors."""
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    # Organization exception handlers

    @app.exception_handler(OrganizationNotFoundError)
    async def organization_not_found_handler(request: Request, exc: OrganizationNotFoundError):
        """Handle organization not found errors."""
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(OrganizationAlreadyExistsError)
    async def organization_already_exists_handler(request: Request, exc: OrganizationAlreadyExistsError):
        """Handle organization already exists errors."""
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(OrganizationSlugAlreadyExistsError)
    async def organization_slug_exists_handler(request: Request, exc: OrganizationSlugAlreadyExistsError):
        """Handle organization slug already exists errors."""
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(OrganizationNameAlreadyExistsError)
    async def organization_name_exists_handler(request: Request, exc: OrganizationNameAlreadyExistsError):
        """Handle organization name already exists errors."""
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(OrganizationMemberNotFoundError)
    async def organization_member_not_found_handler(request: Request, exc: OrganizationMemberNotFoundError):
        """Handle organization member not found errors."""
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(OrganizationMemberAlreadyExistsError)
    async def organization_member_exists_handler(request: Request, exc: OrganizationMemberAlreadyExistsError):
        """Handle organization member already exists errors."""
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(TenantCannotBeDeletedError)
    async def tenant_cannot_be_deleted_handler(request: Request, exc: TenantCannotBeDeletedError):
        """Handle tenant cannot be deleted errors."""
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(OrganizationError)
    async def organization_error_handler(request: Request, exc: OrganizationError):
        """Handle general organization errors."""
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    # Custom Group exception handlers

    @app.exception_handler(CustomGroupNotFoundError)
    async def custom_group_not_found_handler(request: Request, exc: CustomGroupNotFoundError):
        """Handle custom group not found errors."""
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(CustomGroupError)
    async def custom_group_error_handler(request: Request, exc: CustomGroupError):
        """Handle general custom group errors."""
        return JSONResponse(status_code=400, content={"detail": str(exc)})
        # Chat agent exception handlers

    @app.exception_handler(ChatAgentNotFoundError)
    async def chat_agent_not_found_handler(request: Request, exc: ChatAgentNotFoundError):
        """Handle chat agent not found errors."""
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    # Chat agent config exception handlers

    @app.exception_handler(ChatAgentConfigValidationError)
    async def chat_agent_config_validation_handler(request: Request, exc: ChatAgentConfigValidationError):
        """Handle chat agent config validation errors."""
        return JSONResponse(status_code=400, content={"detail": exc.message, "errors": exc.errors})

    @app.exception_handler(UnsupportedChatAgentTypeError)
    async def unsupported_chat_agent_type_handler(request: Request, exc: UnsupportedChatAgentTypeError):
        """Handle unsupported chat agent type errors."""
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(InvalidCredentialError)
    async def invalid_credential_handler(request: Request, exc: InvalidCredentialError):
        """Handle invalid credential errors."""
        return JSONResponse(status_code=400, content={"detail": exc.message, "credential_id": exc.credential_id})

    @app.exception_handler(InvalidAIModelReferenceError)
    async def invalid_ai_model_reference_handler(request: Request, exc: InvalidAIModelReferenceError):
        """Handle invalid AI model reference errors."""
        return JSONResponse(status_code=400, content={"detail": exc.message, "ai_model_id": exc.ai_model_id})

    # Credential validation exception handlers

    @app.exception_handler(CredentialValidationError)
    async def credential_validation_handler(request: Request, exc: CredentialValidationError):
        """Handle credential validation errors."""
        return JSONResponse(status_code=400, content={"detail": exc.message, "errors": exc.errors})

    @app.exception_handler(UnsupportedCredentialTypeError)
    async def unsupported_credential_type_handler(request: Request, exc: UnsupportedCredentialTypeError):
        """Handle unsupported credential type errors."""
        return JSONResponse(status_code=400, content={"detail": str(exc)})
        # Credential exception handlers

    @app.exception_handler(CredentialNotFoundError)
    async def credential_not_found_handler(request: Request, exc: CredentialNotFoundError):
        """Handle credential not found errors."""
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    # Conversation exception handlers

    @app.exception_handler(ConversationNotFoundError)
    async def conversation_not_found_handler(request: Request, exc: ConversationNotFoundError):
        """Handle conversation not found errors."""
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    # Workflow exception handlers

    @app.exception_handler(WorkflowNotFoundError)
    async def workflow_not_found_handler(request: Request, exc: WorkflowNotFoundError):
        """Handle workflow not found errors."""
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    # Chat Widget exception handlers

    @app.exception_handler(ChatWidgetNotFoundError)
    async def chat_widget_not_found_handler(request: Request, exc: ChatWidgetNotFoundError):
        """Handle chat widget not found errors."""
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    # External App exception handlers

    @app.exception_handler(ExternalAppNotFoundError)
    async def external_app_not_found_handler(request: Request, exc: ExternalAppNotFoundError):
        """Handle external app not found errors."""
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ExternalAppAlreadyExistsError)
    async def external_app_already_exists_handler(request: Request, exc: ExternalAppAlreadyExistsError):
        """Handle external app already exists errors."""
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    # File exception handlers

    @app.exception_handler(FileNotFoundByIdError)
    async def file_not_found_handler(request: Request, exc: FileNotFoundByIdError):
        """Handle file not found errors."""
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(FileTooLargeError)
    async def file_too_large_handler(request: Request, exc: FileTooLargeError):
        """Handle file too large errors."""
        return JSONResponse(status_code=413, content={"detail": str(exc)})

    @app.exception_handler(FileStorageNotConfiguredError)
    async def file_storage_not_configured_handler(request: Request, exc: FileStorageNotConfiguredError):
        """Handle file storage not configured errors."""
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    # Tag exception handlers

    @app.exception_handler(TagNotFoundError)
    async def tag_not_found_handler(request: Request, exc: TagNotFoundError):
        """Handle tag not found errors."""
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(TagDeleteNotAllowedError)
    async def tag_delete_not_allowed_handler(request: Request, exc: TagDeleteNotAllowedError):
        """Handle tag delete not allowed errors."""
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(PrincipalNotFoundError)
    async def principal_not_found_handler(request: Request, exc: PrincipalNotFoundError):
        """Handle principal not found errors."""
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    # Tool exception handlers

    @app.exception_handler(ToolNotFoundError)
    async def tool_not_found_handler(request: Request, exc: ToolNotFoundError):
        """Handle tool not found errors."""
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ToolConfigValidationError)
    async def tool_config_validation_handler(request: Request, exc: ToolConfigValidationError):
        """Handle tool config validation errors."""
        return JSONResponse(status_code=400, content={"detail": exc.message, "errors": exc.errors})

    @app.exception_handler(UnsupportedToolTypeError)
    async def unsupported_tool_type_handler(request: Request, exc: UnsupportedToolTypeError):
        """Handle unsupported tool type errors."""
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(InvalidToolCredentialError)
    async def invalid_tool_credential_handler(request: Request, exc: InvalidToolCredentialError):
        """Handle invalid tool credential errors."""
        return JSONResponse(status_code=400, content={"detail": str(exc), "credential_id": exc.credential_id})

    @app.exception_handler(TenantAIModelNotFoundError)
    async def tenant_ai_model_not_found_handler(request: Request, exc: TenantAIModelNotFoundError):
        """Handle tenant AI model not found errors."""
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(TenantAIModelConfigValidationError)
    async def tenant_ai_model_config_validation_handler(request: Request, exc: TenantAIModelConfigValidationError):
        """Handle tenant AI model config validation errors."""
        return JSONResponse(status_code=400, content={"detail": exc.message})

    @app.exception_handler(UnsupportedAIModelProviderError)
    async def unsupported_ai_model_provider_handler(request: Request, exc: UnsupportedAIModelProviderError):
        """Handle unsupported AI model provider errors."""
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(InvalidAIModelCredentialError)
    async def invalid_ai_model_credential_handler(request: Request, exc: InvalidAIModelCredentialError):
        """Handle invalid AI model credential errors."""
        return JSONResponse(status_code=400, content={"detail": str(exc), "credential_id": exc.credential_id})

    # Auth exception handlers

    @app.exception_handler(InvalidCredentialsError)
    async def invalid_credentials_handler(request: Request, exc: InvalidCredentialsError):
        """Handle invalid credentials errors."""
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    @app.exception_handler(InvalidRefreshTokenError)
    async def invalid_refresh_token_handler(request: Request, exc: InvalidRefreshTokenError):
        """Handle invalid refresh token errors."""
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    @app.exception_handler(LDAPConnectionError)
    async def ldap_connection_handler(request: Request, exc: LDAPConnectionError):
        """Handle LDAP connection errors."""
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(AuthError)
    async def auth_error_handler(request: Request, exc: AuthError):
        """Handle general auth errors."""
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    # Include routers
    app.include_router(auth.router, prefix="/api/v1/platform-service/auth", tags=["Authentication"])

    app.include_router(health.router, prefix="/api/v1/platform-service", tags=["Health"])

    app.include_router(identity.router, prefix="/api/v1/platform-service/identity", tags=["Identity"])

    app.include_router(organizations.router, prefix="/api/v1/platform-service/organizations", tags=["Organizations"])

    app.include_router(tenants.router, prefix="/api/v1/platform-service/tenants", tags=["Tenants"])

    app.include_router(
        principals.router, prefix="/api/v1/platform-service/tenants/{tenant_id}/principals", tags=["Principals"]
    )

    app.include_router(
        custom_groups.router,
        prefix="/api/v1/platform-service/tenants/{tenant_id}/custom-groups",
        tags=["Custom Groups"],
    )

    # Resource type tags list routes - MUST be before resource routers to avoid path conflicts
    # e.g., /chat-agents/tags must be matched before /chat-agents/{chat_agent_id}
    app.include_router(
        tags.credentials_tags_list_router, prefix="/api/v1/platform-service/tenants/{tenant_id}", tags=["Credentials"]
    )

    app.include_router(credentials.router, prefix="/api/v1/platform-service/tenants/{tenant_id}", tags=["Credentials"])

    app.include_router(
        tags.chat_agents_tags_list_router, prefix="/api/v1/platform-service/tenants/{tenant_id}", tags=["Chat Agents"]
    )

    app.include_router(chat_agents.router, prefix="/api/v1/platform-service/tenants/{tenant_id}", tags=["Chat Agents"])

    app.include_router(
        conversations.router, prefix="/api/v1/platform-service/tenants/{tenant_id}", tags=["Conversations"]
    )

    app.include_router(
        tags.workflows_tags_list_router,
        prefix="/api/v1/platform-service/tenants/{tenant_id}",
        tags=["Workflows"],
    )

    app.include_router(workflows.router, prefix="/api/v1/platform-service/tenants/{tenant_id}", tags=["Workflows"])

    app.include_router(
        tags.chat_widgets_tags_list_router, prefix="/api/v1/platform-service/tenants/{tenant_id}", tags=["Chat Widgets"]
    )

    app.include_router(
        chat_widgets.router, prefix="/api/v1/platform-service/tenants/{tenant_id}", tags=["Chat Widgets"]
    )

    # Tags routes
    app.include_router(tags.router, prefix="/api/v1/platform-service/tenants/{tenant_id}", tags=["Tags"])

    # Resource-specific tag routes
    app.include_router(
        tags.chat_agent_tags_router, prefix="/api/v1/platform-service/tenants/{tenant_id}", tags=["Chat Agents"]
    )

    app.include_router(
        tags.workflow_tags_router,
        prefix="/api/v1/platform-service/tenants/{tenant_id}",
        tags=["Workflows"],
    )

    app.include_router(
        tags.chat_widget_tags_router, prefix="/api/v1/platform-service/tenants/{tenant_id}", tags=["Chat Widgets"]
    )

    app.include_router(
        tags.credential_tags_router, prefix="/api/v1/platform-service/tenants/{tenant_id}", tags=["Credentials"]
    )

    # Tools routes - tags list router MUST be before tools router to avoid path conflicts
    app.include_router(
        tags.tools_tags_list_router, prefix="/api/v1/platform-service/tenants/{tenant_id}", tags=["Tools"]
    )

    app.include_router(tools.router, prefix="/api/v1/platform-service/tenants/{tenant_id}", tags=["Tools"])

    # Tool-specific tag routes
    app.include_router(tags.tool_tags_router, prefix="/api/v1/platform-service/tenants/{tenant_id}", tags=["Tools"])

    # User Favorites routes
    app.include_router(
        user_favorites.router, prefix="/api/v1/platform-service/tenants/{tenant_id}", tags=["User Favorites"]
    )

    # Tenant AI Models routes
    app.include_router(
        tenant_ai_models.router, prefix="/api/v1/platform-service/tenants/{tenant_id}", tags=["Tenant AI Models"]
    )

    # AI Model tag routes
    app.include_router(
        tags.ai_models_tags_list_router,
        prefix="/api/v1/platform-service/tenants/{tenant_id}",
        tags=["Tenant AI Models"],
    )

    app.include_router(
        tags.ai_model_tags_router, prefix="/api/v1/platform-service/tenants/{tenant_id}", tags=["Tenant AI Models"]
    )

    # External Apps routes - tags list router MUST be before external apps router to avoid path conflicts
    app.include_router(
        tags.external_apps_tags_list_router,
        prefix="/api/v1/platform-service/tenants/{tenant_id}",
        tags=["External Apps"],
    )

    app.include_router(
        external_apps.router, prefix="/api/v1/platform-service/tenants/{tenant_id}", tags=["External Apps"]
    )

    # External App tag routes
    app.include_router(
        tags.external_app_tags_router, prefix="/api/v1/platform-service/tenants/{tenant_id}", tags=["External Apps"]
    )

    # Dashboard routes
    app.include_router(dashboard.router, prefix="/api/v1/platform-service/tenants/{tenant_id}", tags=["Dashboard"])

    # Config Suggestions routes
    app.include_router(
        config_suggestions.router, prefix="/api/v1/platform-service/tenants/{tenant_id}", tags=["Config Suggestions"]
    )

    # Foundry Agent Discovery routes
    app.include_router(foundry.router, prefix="/api/v1/platform-service/tenants/{tenant_id}", tags=["Foundry"])

    # N8N Workflow Browser routes
    app.include_router(n8n.router, prefix="/api/v1/platform-service/tenants/{tenant_id}", tags=["N8N"])

    # Search routes
    app.include_router(search.router, prefix="/api/v1/platform-service/tenants/{tenant_id}", tags=["Search"])

    # Recent Visits routes
    app.include_router(
        recent_visits.router, prefix="/api/v1/platform-service/tenants/{tenant_id}", tags=["Recent Visits"]
    )

    # Files routes
    app.include_router(files.router, prefix="/api/v1/platform-service/tenants/{tenant_id}", tags=["Files"])

    return app


app = create_app()
