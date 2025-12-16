from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aihub.apis.v1 import healthcheck, identity, tenants
from aihub.database.dependencies import close_db_client


load_dotenv()


def create_app() -> FastAPI:
    """Create and configure FastAPI application following best practices."""
    
    app = FastAPI(
        title="AIHub API",
        description="AIHub - AI Application Management Platform",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )
    
    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production: specify allowed origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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
