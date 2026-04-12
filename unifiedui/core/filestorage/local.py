"""Local filesystem file storage implementation."""

import io
import json
from pathlib import Path
from typing import BinaryIO

from unifiedui.core.filestorage.base import BaseFileStorage


class LocalFileStorage(BaseFileStorage):
    """File storage implementation using the local filesystem."""

    def __init__(self, base_path: str) -> None:
        """Initialize local file storage.

        Args:
            base_path: Root directory for file storage.

        """
        self._base_path = Path(base_path)
        self._base_path.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, storage_path: str) -> Path:
        """Resolve and validate a storage path against the base directory.

        Args:
            storage_path: Relative storage path.

        Returns:
            Resolved absolute path.

        Raises:
            ValueError: If the resolved path escapes the base directory.

        """
        resolved = (self._base_path / storage_path).resolve()
        if not str(resolved).startswith(str(self._base_path.resolve())):
            raise ValueError("Invalid storage path: path traversal detected")
        return resolved

    def _meta_path(self, file_path: Path) -> Path:
        """Get the metadata sidecar path for a file.

        Args:
            file_path: Path to the data file.

        Returns:
            Path to the corresponding .meta JSON file.

        """
        return file_path.with_suffix(file_path.suffix + ".meta")

    def upload(self, storage_path: str, data: BinaryIO, content_type: str) -> None:
        """Upload a file to the local filesystem.

        Args:
            storage_path: Relative path within the storage root.
            data: Binary file data stream.
            content_type: MIME type of the file.

        """
        file_path = self._resolve_path(storage_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "wb") as f:
            while chunk := data.read(8192):
                f.write(chunk)

        meta = {"content_type": content_type}
        with open(self._meta_path(file_path), "w") as mf:
            json.dump(meta, mf)

    def download(self, storage_path: str) -> tuple[BinaryIO, str]:
        """Download a file from the local filesystem.

        Args:
            storage_path: Relative path within the storage root.

        Returns:
            Tuple of (binary data stream, content_type).

        Raises:
            FileNotFoundError: If the file does not exist.

        """
        file_path = self._resolve_path(storage_path)
        if not file_path.is_file():
            raise FileNotFoundError(f"File not found: {storage_path}")

        content_type = "application/octet-stream"
        meta_file = self._meta_path(file_path)
        if meta_file.is_file():
            with open(meta_file) as mf:
                meta = json.load(mf)
                content_type = meta.get("content_type", content_type)

        data = file_path.read_bytes()
        return io.BytesIO(data), content_type

    def delete(self, storage_path: str) -> None:
        """Delete a file from the local filesystem.

        Args:
            storage_path: Relative path within the storage root.

        """
        file_path = self._resolve_path(storage_path)
        if file_path.is_file():
            file_path.unlink()
        meta_file = self._meta_path(file_path)
        if meta_file.is_file():
            meta_file.unlink()

    def exists(self, storage_path: str) -> bool:
        """Check if a file exists on the local filesystem.

        Args:
            storage_path: Relative path within the storage root.

        Returns:
            True if file exists, False otherwise.

        """
        file_path = self._resolve_path(storage_path)
        return file_path.is_file()
