from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aihub.apis.v1 import healthcheck, identity


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
    
    return app


app = create_app()
