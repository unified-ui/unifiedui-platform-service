from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from unifiedui.apis.v1 import health, identity, tenants, custom_groups, credentials, applications, conversations, autonomous_agents, chat_widgets, tags, user_favorites, principals, tools, tenant_ai_models
from unifiedui.exc.autonomous_agents import AutonomousAgentNotFoundError
from unifiedui.exc.custom_groups import CustomGroupNotFoundError, CustomGroupError
from unifiedui.exc.applications import ApplicationNotFoundError
from unifiedui.exc.credentials import CredentialNotFoundError
from unifiedui.exc.conversations import ConversationNotFoundError
from unifiedui.exc.chat_widgets import ChatWidgetNotFoundError
from unifiedui.exc.tools import ToolNotFoundError, ToolConfigValidationError, UnsupportedToolTypeError, InvalidToolCredentialError
from unifiedui.exc.tenant_ai_models import (
    TenantAIModelNotFoundError,
    TenantAIModelConfigValidationError,
    UnsupportedAIModelProviderError,
    InvalidAIModelCredentialError,
)
from unifiedui.exc.principal import PrincipalNotFoundError
from unifiedui.exc.tags import TagNotFoundError, TagDeleteNotAllowedError
from unifiedui.exc.application_config import (
    ApplicationConfigValidationError,
    UnsupportedApplicationTypeError,
    InvalidCredentialError
)
from unifiedui.handlers.validators.credential_validator import (
    CredentialValidationError,
    UnsupportedCredentialTypeError,
)

from unifiedui.core.config import settings
from unifiedui.exc.tenants import TenantNotFoundError, TenantError
from unifiedui.exc.permissions import PermissionDeniedError
from unifiedui.logger import setup_logging, get_logger


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
        openapi_url="/openapi.json"
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
        return JSONResponse(
            status_code=403,
            content={"detail": str(exc)}
        )
    
    @app.exception_handler(TenantNotFoundError)
    async def tenant_not_found_handler(request: Request, exc: TenantNotFoundError):
        """Handle tenant not found errors."""
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc)}
        )
    
    @app.exception_handler(TenantError)
    async def tenant_error_handler(request: Request, exc: TenantError):
        """Handle general tenant errors."""
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)}
        )
    
    # Custom Group exception handlers
    
    @app.exception_handler(CustomGroupNotFoundError)
    async def custom_group_not_found_handler(request: Request, exc: CustomGroupNotFoundError):
        """Handle custom group not found errors."""
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc)}
        )
    
    @app.exception_handler(CustomGroupError)
    async def custom_group_error_handler(request: Request, exc: CustomGroupError):
        """Handle general custom group errors."""
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)}
        )
        # Application exception handlers
    
    @app.exception_handler(ApplicationNotFoundError)
    async def application_not_found_handler(request: Request, exc: ApplicationNotFoundError):
        """Handle application not found errors."""
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc)}
        )
    
    # Application config exception handlers
    
    @app.exception_handler(ApplicationConfigValidationError)
    async def application_config_validation_handler(request: Request, exc: ApplicationConfigValidationError):
        """Handle application config validation errors."""
        return JSONResponse(
            status_code=400,
            content={"detail": exc.message, "errors": exc.errors}
        )
    
    @app.exception_handler(UnsupportedApplicationTypeError)
    async def unsupported_application_type_handler(request: Request, exc: UnsupportedApplicationTypeError):
        """Handle unsupported application type errors."""
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)}
        )
    
    @app.exception_handler(InvalidCredentialError)
    async def invalid_credential_handler(request: Request, exc: InvalidCredentialError):
        """Handle invalid credential errors."""
        return JSONResponse(
            status_code=400,
            content={"detail": exc.message, "credential_id": exc.credential_id}
        )
    
    # Credential validation exception handlers
    
    @app.exception_handler(CredentialValidationError)
    async def credential_validation_handler(request: Request, exc: CredentialValidationError):
        """Handle credential validation errors."""
        return JSONResponse(
            status_code=400,
            content={"detail": exc.message, "errors": exc.errors}
        )
    
    @app.exception_handler(UnsupportedCredentialTypeError)
    async def unsupported_credential_type_handler(request: Request, exc: UnsupportedCredentialTypeError):
        """Handle unsupported credential type errors."""
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)}
        )
        # Credential exception handlers
    
    @app.exception_handler(CredentialNotFoundError)
    async def credential_not_found_handler(request: Request, exc: CredentialNotFoundError):
        """Handle credential not found errors."""
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc)}
        )
    
    # Conversation exception handlers
    
    @app.exception_handler(ConversationNotFoundError)
    async def conversation_not_found_handler(request: Request, exc: ConversationNotFoundError):
        """Handle conversation not found errors."""
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc)}
        )
    
    # Autonomous Agent exception handlers
    
    @app.exception_handler(AutonomousAgentNotFoundError)
    async def autonomous_agent_not_found_handler(request: Request, exc: AutonomousAgentNotFoundError):
        """Handle autonomous agent not found errors."""
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc)}
        )
    
    # Chat Widget exception handlers
    
    @app.exception_handler(ChatWidgetNotFoundError)
    async def chat_widget_not_found_handler(request: Request, exc: ChatWidgetNotFoundError):
        """Handle chat widget not found errors."""
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc)}
        )
    
    # Tag exception handlers
    
    @app.exception_handler(TagNotFoundError)
    async def tag_not_found_handler(request: Request, exc: TagNotFoundError):
        """Handle tag not found errors."""
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc)}
        )
    
    @app.exception_handler(TagDeleteNotAllowedError)
    async def tag_delete_not_allowed_handler(request: Request, exc: TagDeleteNotAllowedError):
        """Handle tag delete not allowed errors."""
        return JSONResponse(
            status_code=403,
            content={"detail": str(exc)}
        )
    
    @app.exception_handler(PrincipalNotFoundError)
    async def principal_not_found_handler(request: Request, exc: PrincipalNotFoundError):
        """Handle principal not found errors."""
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc)}
        )
    
    # Tool exception handlers
    
    @app.exception_handler(ToolNotFoundError)
    async def tool_not_found_handler(request: Request, exc: ToolNotFoundError):
        """Handle tool not found errors."""
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc)}
        )
    
    @app.exception_handler(ToolConfigValidationError)
    async def tool_config_validation_handler(request: Request, exc: ToolConfigValidationError):
        """Handle tool config validation errors."""
        return JSONResponse(
            status_code=400,
            content={"detail": exc.message, "errors": exc.errors}
        )
    
    @app.exception_handler(UnsupportedToolTypeError)
    async def unsupported_tool_type_handler(request: Request, exc: UnsupportedToolTypeError):
        """Handle unsupported tool type errors."""
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)}
        )
    
    @app.exception_handler(InvalidToolCredentialError)
    async def invalid_tool_credential_handler(request: Request, exc: InvalidToolCredentialError):
        """Handle invalid tool credential errors."""
        return JSONResponse(
            status_code=400,
            content={"detail": exc.message, "credential_id": exc.credential_id}
        )

    @app.exception_handler(TenantAIModelNotFoundError)
    async def tenant_ai_model_not_found_handler(request: Request, exc: TenantAIModelNotFoundError):
        """Handle tenant AI model not found errors."""
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc)}
        )

    @app.exception_handler(TenantAIModelConfigValidationError)
    async def tenant_ai_model_config_validation_handler(request: Request, exc: TenantAIModelConfigValidationError):
        """Handle tenant AI model config validation errors."""
        return JSONResponse(
            status_code=400,
            content={"detail": exc.message}
        )

    @app.exception_handler(UnsupportedAIModelProviderError)
    async def unsupported_ai_model_provider_handler(request: Request, exc: UnsupportedAIModelProviderError):
        """Handle unsupported AI model provider errors."""
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)}
        )

    @app.exception_handler(InvalidAIModelCredentialError)
    async def invalid_ai_model_credential_handler(request: Request, exc: InvalidAIModelCredentialError):
        """Handle invalid AI model credential errors."""
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc), "credential_id": exc.credential_id}
        )

    # Include routers
    app.include_router(
        health.router,
        prefix="/api/v1/platform-service",
        tags=["Health"]
    )
    
    app.include_router(
        identity.router,
        prefix="/api/v1/platform-service/identity",
        tags=["Identity"]
    )
    
    app.include_router(
        tenants.router,
        prefix="/api/v1/platform-service/tenants",
        tags=["Tenants"]
    )
    
    app.include_router(
        principals.router,
        prefix="/api/v1/platform-service/tenants/{tenant_id}/principals",
        tags=["Principals"]
    )
    
    app.include_router(
        custom_groups.router,
        prefix="/api/v1/platform-service/tenants/{tenant_id}/custom-groups",
        tags=["Custom Groups"]
    )
    
    # Resource type tags list routes - MUST be before resource routers to avoid path conflicts
    # e.g., /applications/tags must be matched before /applications/{application_id}
    app.include_router(
        tags.credentials_tags_list_router,
        prefix="/api/v1/platform-service/tenants/{tenant_id}",
        tags=["Credentials"]
    )
    
    app.include_router(
        credentials.router,
        prefix="/api/v1/platform-service/tenants/{tenant_id}",
        tags=["Credentials"]
    )
    
    app.include_router(
        tags.applications_tags_list_router,
        prefix="/api/v1/platform-service/tenants/{tenant_id}",
        tags=["Applications"]
    )
    
    app.include_router(
        applications.router,
        prefix="/api/v1/platform-service/tenants/{tenant_id}",
        tags=["Applications"]
    )
    
    app.include_router(
        conversations.router,
        prefix="/api/v1/platform-service/tenants/{tenant_id}",
        tags=["Conversations"]
    )
    
    app.include_router(
        tags.autonomous_agents_tags_list_router,
        prefix="/api/v1/platform-service/tenants/{tenant_id}",
        tags=["Autonomous Agents"]
    )
    
    app.include_router(
        autonomous_agents.router,
        prefix="/api/v1/platform-service/tenants/{tenant_id}",
        tags=["Autonomous Agents"]
    )
    
    app.include_router(
        tags.chat_widgets_tags_list_router,
        prefix="/api/v1/platform-service/tenants/{tenant_id}",
        tags=["Chat Widgets"]
    )
    
    app.include_router(
        chat_widgets.router,
        prefix="/api/v1/platform-service/tenants/{tenant_id}",
        tags=["Chat Widgets"]
    )
    
    # Tags routes
    app.include_router(
        tags.router,
        prefix="/api/v1/platform-service/tenants/{tenant_id}",
        tags=["Tags"]
    )
    
    # Resource-specific tag routes
    app.include_router(
        tags.application_tags_router,
        prefix="/api/v1/platform-service/tenants/{tenant_id}",
        tags=["Applications"]
    )
    
    app.include_router(
        tags.autonomous_agent_tags_router,
        prefix="/api/v1/platform-service/tenants/{tenant_id}",
        tags=["Autonomous Agents"]
    )
    
    app.include_router(
        tags.chat_widget_tags_router,
        prefix="/api/v1/platform-service/tenants/{tenant_id}",
        tags=["Chat Widgets"]
    )
    
    app.include_router(
        tags.credential_tags_router,
        prefix="/api/v1/platform-service/tenants/{tenant_id}",
        tags=["Credentials"]
    )
    
    # Tools routes - tags list router MUST be before tools router to avoid path conflicts
    app.include_router(
        tags.tools_tags_list_router,
        prefix="/api/v1/platform-service/tenants/{tenant_id}",
        tags=["Tools"]
    )
    
    app.include_router(
        tools.router,
        prefix="/api/v1/platform-service/tenants/{tenant_id}",
        tags=["Tools"]
    )
    
    # Tool-specific tag routes
    app.include_router(
        tags.tool_tags_router,
        prefix="/api/v1/platform-service/tenants/{tenant_id}",
        tags=["Tools"]
    )
    
    # User Favorites routes
    app.include_router(
        user_favorites.router,
        prefix="/api/v1/platform-service/tenants/{tenant_id}",
        tags=["User Favorites"]
    )
    
    # Tenant AI Models routes
    app.include_router(
        tenant_ai_models.router,
        prefix="/api/v1/platform-service/tenants/{tenant_id}",
        tags=["Tenant AI Models"]
    )
    
    return app


app = create_app()
