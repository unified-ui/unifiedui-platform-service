"""File storage dependency for FastAPI handlers."""

from unifiedui.core.config import settings
from unifiedui.core.filestorage.base import BaseFileStorage
from unifiedui.core.filestorage.factory import FileStorageFactory
from unifiedui.logger import get_logger

logger = get_logger(__name__)

_file_storage_client: BaseFileStorage | None = None
_file_storage_initialized: bool = False


def get_file_storage_client() -> BaseFileStorage | None:
    """Get the global file storage client instance.

    File storage is optional — returns None if not configured.

    Returns:
        BaseFileStorage instance or None if not configured.

    """
    global _file_storage_client, _file_storage_initialized

    if _file_storage_initialized:
        return _file_storage_client

    _file_storage_initialized = True

    if not settings.file_storage_type:
        logger.info("File storage is disabled (FILE_STORAGE_TYPE not set)")
        return None

    try:
        _file_storage_client = FileStorageFactory.create(
            storage_type=settings.file_storage_type,
            base_path=settings.file_storage_local_base_path,
            account_url=settings.file_storage_azure_blob_account_url,
            container_name=settings.file_storage_azure_blob_container,
        )
        logger.info("File storage client initialized successfully (%s)", settings.file_storage_type)
    except Exception as e:
        logger.warning("Failed to initialize file storage client: %s. Continuing without file storage.", e)
        _file_storage_client = None

    return _file_storage_client
