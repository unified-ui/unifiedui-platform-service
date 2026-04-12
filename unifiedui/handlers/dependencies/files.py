"""File handler dependency for FastAPI."""

from fastapi import Depends

from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.core.filestorage.base import BaseFileStorage
from unifiedui.handlers.dependencies.database import get_db_client
from unifiedui.handlers.dependencies.filestorage import get_file_storage_client
from unifiedui.handlers.files import FileHandler


def get_file_handler(
    db_client: SQLAlchemyClient = Depends(get_db_client),
    file_storage_client: BaseFileStorage | None = Depends(get_file_storage_client),
) -> FileHandler:
    """Get a FileHandler instance as a dependency.

    Args:
        db_client: SQLAlchemy database client dependency.
        file_storage_client: Optional file storage client dependency.

    Returns:
        FileHandler instance.

    """
    return FileHandler(db_client, file_storage_client)
