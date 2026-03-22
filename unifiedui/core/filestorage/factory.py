"""Factory for creating file storage clients."""

from unifiedui.core.filestorage.base import BaseFileStorage
from unifiedui.logger import get_logger

logger = get_logger(__name__)

FILE_STORAGE_TYPE_LOCAL = "local"
FILE_STORAGE_TYPE_AZURE_BLOB = "azureblob"


class FileStorageFactory:
    """Factory for creating file storage backend instances."""

    @staticmethod
    def create(storage_type: str, **kwargs: str | None) -> BaseFileStorage:
        """Create a file storage client based on the configured type.

        Args:
            storage_type: Storage backend type ("local" or "azureblob").
            **kwargs: Backend-specific configuration parameters.

        Returns:
            Configured BaseFileStorage instance.

        Raises:
            ValueError: If the storage type is not supported.

        """
        if storage_type == FILE_STORAGE_TYPE_LOCAL:
            from unifiedui.core.filestorage.local import LocalFileStorage

            base_path = kwargs.get("base_path")
            if not base_path:
                raise ValueError("base_path is required for local file storage")
            logger.info("Creating local file storage at: %s", base_path)
            return LocalFileStorage(base_path=base_path)

        if storage_type == FILE_STORAGE_TYPE_AZURE_BLOB:
            from unifiedui.core.filestorage.azureblob import AzureBlobFileStorage

            container_name = kwargs.get("container_name")
            account_url = kwargs.get("account_url")
            if not container_name or not account_url:
                raise ValueError("account_url and container_name are required for Azure Blob file storage")
            logger.info("Creating Azure Blob file storage (container: %s)", container_name)
            return AzureBlobFileStorage(account_url=account_url, container_name=container_name)

        raise ValueError(f"Unsupported file storage type: {storage_type}")
