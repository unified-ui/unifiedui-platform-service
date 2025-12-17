"""FastAPI dependencies for handlers."""
from fastapi import Depends

from aihub.core.database.client import SQLAlchemyClient
from aihub.core.database.config import DatabaseConfig
from aihub.core.handlers.tenants import TenantHandler

# Global SQLAlchemy client instance
_db_client: SQLAlchemyClient | None = None


def get_db_client() -> SQLAlchemyClient:
    """
    Get the global SQLAlchemy client instance.
    
    Returns:
        SQLAlchemyClient instance
    """
    global _db_client
    if _db_client is None:
        config = DatabaseConfig.from_env()
        _db_client = SQLAlchemyClient(config=config)
    return _db_client


def get_tenant_handler(
    db_client: SQLAlchemyClient = Depends(get_db_client)
) -> TenantHandler:
    """
    Get a TenantHandler instance as a dependency.
    
    Args:
        db_client: SQLAlchemy database client dependency
        
    Returns:
        TenantHandler instance
    """
    return TenantHandler(db_client)
