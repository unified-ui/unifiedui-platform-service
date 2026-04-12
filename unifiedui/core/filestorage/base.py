"""Abstract base class for file storage backends."""

from abc import ABC, abstractmethod
from typing import BinaryIO


class BaseFileStorage(ABC):
    """Abstract base class for file storage mechanisms."""

    @abstractmethod
    def upload(self, storage_path: str, data: BinaryIO, content_type: str) -> None:
        """Upload a file to the storage backend.

        Args:
            storage_path: Relative path within the storage root (e.g. "tenant-id/chat_attachment/uuid.png").
            data: Binary file data stream.
            content_type: MIME type of the file.

        """
        pass

    @abstractmethod
    def download(self, storage_path: str) -> tuple[BinaryIO, str]:
        """Download a file from the storage backend.

        Args:
            storage_path: Relative path within the storage root.

        Returns:
            Tuple of (binary data stream, content_type).

        Raises:
            FileNotFoundError: If the file does not exist.

        """
        pass

    @abstractmethod
    def delete(self, storage_path: str) -> None:
        """Delete a file from the storage backend.

        Args:
            storage_path: Relative path within the storage root.

        """
        pass

    @abstractmethod
    def exists(self, storage_path: str) -> bool:
        """Check if a file exists in the storage backend.

        Args:
            storage_path: Relative path within the storage root.

        Returns:
            True if file exists, False otherwise.

        """
        pass
