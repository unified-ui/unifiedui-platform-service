import logging
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from aihub.apis.v1 import healthcheck, identity, tenants
from aihub.database.dependencies import close_db_client
from aihub.core.config import settings
from aihub.exc.tenants import TenantNotFoundError, TenantError


# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

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
    
    # Include routers
    app.include_router(
        healthcheck.router,
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
    
    # Lifecycle events
    @app.on_event("shutdown")
    async def shutdown_event():
        """Close database connection on shutdown."""
        close_db_client()
    
    return app


app = create_app()
