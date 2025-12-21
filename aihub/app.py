from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from aihub.apis.v1 import health, identity, tenants, custom_groups, credentials, applications, conversations, autonomous_agents
from aihub.exc.autonomous_agents import AutonomousAgentNotFoundError
from aihub.exc.custom_groups import CustomGroupNotFoundError, CustomGroupError
from aihub.exc.applications import ApplicationNotFoundError
from aihub.exc.credentials import CredentialNotFoundError
from aihub.exc.conversations import ConversationNotFoundError

from aihub.core.config import settings
from aihub.exc.tenants import TenantNotFoundError, TenantError
from aihub.exc.permissions import PermissionDeniedError
from aihub.logger import setup_logging, get_logger


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
    
    # Include routers
    app.include_router(
        health.router,
        prefix="/api/v1",
        tags=["Health"]
    )
    
    app.include_router(
        identity.router,
        prefix="/api/v1/identity",
        tags=["Identity"]
    )
    
    app.include_router(
        tenants.router,
        prefix="/api/v1/tenants",
        tags=["Tenants"]
    )
    
    app.include_router(
        custom_groups.router,
        prefix="/api/v1/tenants/{tenant_id}/custom-groups",
        tags=["Custom Groups"]
    )
    
    app.include_router(
        credentials.router,
        prefix="/api/v1/tenants/{tenant_id}",
        tags=["Credentials"]
    )
    
    app.include_router(
        applications.router,
        prefix="/api/v1/tenants/{tenant_id}",
        tags=["Applications"]
    )
    
    app.include_router(
        conversations.router,
        prefix="/api/v1/tenants/{tenant_id}",
        tags=["Conversations"]
    )
    
    app.include_router(
        autonomous_agents.router,
        prefix="/api/v1/tenants/{tenant_id}",
        tags=["Autonomous Agents"]
    )
    
    return app


app = create_app()
