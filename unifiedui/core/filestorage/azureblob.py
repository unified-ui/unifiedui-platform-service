"""Azure Blob Storage file storage implementation."""

import io
from typing import BinaryIO

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings

from unifiedui.core.filestorage.base import BaseFileStorage


class AzureBlobFileStorage(BaseFileStorage):
    """File storage implementation using Azure Blob Storage with Managed Identity."""

    def __init__(self, account_url: str, container_name: str) -> None:
        """Initialize Azure Blob file storage.

        Args:
            account_url: Azure Storage account URL (e.g. "https://account.blob.core.windows.net").
            container_name: Name of the blob container.

        """
        credential = DefaultAzureCredential()
        self._blob_service = BlobServiceClient(account_url=account_url, credential=credential)
        self._container_name = container_name

    def upload(self, storage_path: str, data: BinaryIO, content_type: str) -> None:
        """Upload a file to Azure Blob Storage.

        Args:
            storage_path: Blob name within the container.
            data: Binary file data stream.
            content_type: MIME type of the file.

        """
        blob_client = self._blob_service.get_blob_client(container=self._container_name, blob=storage_path)
        content_settings = ContentSettings(content_type=content_type)
        blob_client.upload_blob(data, overwrite=True, content_settings=content_settings)

    def download(self, storage_path: str) -> tuple[BinaryIO, str]:
        """Download a file from Azure Blob Storage.

        Args:
            storage_path: Blob name within the container.

        Returns:
            Tuple of (binary data stream, content_type).

        Raises:
            FileNotFoundError: If the blob does not exist.

        """
        blob_client = self._blob_service.get_blob_client(container=self._container_name, blob=storage_path)
        try:
            download_stream = blob_client.download_blob()
            properties = download_stream.properties
            content_type = properties.content_settings.content_type or "application/octet-stream"
            data = download_stream.readall()
            return io.BytesIO(data), content_type
        except Exception as e:
            if "BlobNotFound" in str(e):
                raise FileNotFoundError(f"File not found: {storage_path}") from e
            raise

    def delete(self, storage_path: str) -> None:
        """Delete a file from Azure Blob Storage.

        Args:
            storage_path: Blob name within the container.

        """
        blob_client = self._blob_service.get_blob_client(container=self._container_name, blob=storage_path)
        blob_client.delete_blob(delete_snapshots="include")

    def exists(self, storage_path: str) -> bool:
        """Check if a file exists in Azure Blob Storage.

        Args:
            storage_path: Blob name within the container.

        Returns:
            True if the blob exists, False otherwise.

        """
        blob_client = self._blob_service.get_blob_client(container=self._container_name, blob=storage_path)
        try:
            blob_client.get_blob_properties()
            return True
        except Exception:
            return False
