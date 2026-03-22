"""Business logic handlers for file operations."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, BinaryIO

from sqlalchemy import select

from unifiedui.core.config import settings
from unifiedui.core.database.models import File
from unifiedui.exc.files import FileNotFoundByIdError, FileStorageNotConfiguredError, FileTooLargeError
from unifiedui.logger import get_logger
from unifiedui.schema.responses.files import FileResponse

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from unifiedui.core.database.client import SQLAlchemyClient
    from unifiedui.core.filestorage.base import BaseFileStorage

logger = get_logger(__name__)


class FileHandler:
    """Handler class for file upload, download, and delete operations."""

    def __init__(
        self,
        db_client: SQLAlchemyClient,
        file_storage_client: BaseFileStorage | None = None,
    ):
        """Initialize the file handler.

        Args:
            db_client: SQLAlchemy database client instance.
            file_storage_client: Optional file storage backend.

        """
        self.db_client = db_client
        self.file_storage_client = file_storage_client

    def _ensure_storage(self) -> BaseFileStorage:
        """Ensure file storage is configured.

        Returns:
            The configured file storage client.

        Raises:
            FileStorageNotConfiguredError: If file storage is not configured.

        """
        if self.file_storage_client is None:
            raise FileStorageNotConfiguredError()
        return self.file_storage_client

    def upload_file(
        self,
        tenant_id: str,
        user_id: str,
        file_name: str,
        file_size: int,
        content_type: str,
        context_type: str,
        context_id: str | None,
        data: BinaryIO,
    ) -> FileResponse:
        """Upload a file and persist metadata.

        Args:
            tenant_id: Tenant ID for scoping.
            user_id: ID of the uploading user.
            file_name: Original file name.
            file_size: Size in bytes.
            content_type: MIME type.
            context_type: Context type (e.g. CHAT_ATTACHMENT, APP_IMAGE).
            context_id: Optional related entity ID.
            data: Binary file data stream.

        Returns:
            File metadata response.

        Raises:
            FileTooLargeError: If file exceeds max size.
            FileStorageNotConfiguredError: If storage not configured.

        """
        storage = self._ensure_storage()

        max_size = settings.file_storage_max_file_size_bytes
        if file_size > max_size:
            raise FileTooLargeError(file_size, max_size)

        file_id = str(uuid.uuid4())
        extension = ""
        if "." in file_name:
            extension = "." + file_name.rsplit(".", 1)[-1].lower()
        storage_path = f"{tenant_id}/{context_type}/{file_id}{extension}"

        logger.info(
            "Uploading file",
            extra={"tenant_id": tenant_id, "file_id": file_id, "file_name": file_name, "storage_path": storage_path},
        )

        storage.upload(storage_path, data, content_type)

        file_record = File(
            id=file_id,
            tenant_id=tenant_id,
            file_name=file_name,
            file_size=file_size,
            content_type=content_type,
            storage_path=storage_path,
            context_type=context_type,
            context_id=context_id,
            created_by=user_id,
            updated_by=user_id,
        )

        with self.db_client.get_session() as session:
            session.add(file_record)
            session.commit()
            session.refresh(file_record)
            return self._to_response(file_record)

    def get_file_metadata(self, tenant_id: str, file_id: str) -> FileResponse:
        """Get file metadata by ID.

        Args:
            tenant_id: Tenant ID for scoping.
            file_id: File ID.

        Returns:
            File metadata response.

        Raises:
            FileNotFoundByIdError: If file not found.

        """
        with self.db_client.get_session() as session:
            file_record = self._get_file(session, tenant_id, file_id)
            return self._to_response(file_record)

    def download_file(self, tenant_id: str, file_id: str) -> tuple[BinaryIO, str, str]:
        """Download a file by ID.

        Args:
            tenant_id: Tenant ID for scoping.
            file_id: File ID.

        Returns:
            Tuple of (binary data stream, content_type, file_name).

        Raises:
            FileNotFoundByIdError: If file not found.
            FileStorageNotConfiguredError: If storage not configured.

        """
        storage = self._ensure_storage()

        with self.db_client.get_session() as session:
            file_record = self._get_file(session, tenant_id, file_id)
            data, content_type = storage.download(file_record.storage_path)
            return data, content_type, file_record.file_name

    def delete_file(self, tenant_id: str, file_id: str) -> None:
        """Delete a file by ID.

        Args:
            tenant_id: Tenant ID for scoping.
            file_id: File ID.

        Raises:
            FileNotFoundByIdError: If file not found.
            FileStorageNotConfiguredError: If storage not configured.

        """
        storage = self._ensure_storage()

        with self.db_client.get_session() as session:
            file_record = self._get_file(session, tenant_id, file_id)
            storage_path = file_record.storage_path

            session.delete(file_record)
            session.commit()

        storage.delete(storage_path)
        logger.info("Deleted file", extra={"tenant_id": tenant_id, "file_id": file_id})

    def _get_file(self, session: Session, tenant_id: str, file_id: str) -> File:
        """Get a file record or raise not found.

        Args:
            session: SQLAlchemy session.
            tenant_id: Tenant ID for scoping.
            file_id: File ID.

        Returns:
            File record.

        Raises:
            FileNotFoundByIdError: If file not found.

        """
        query = select(File).where(File.tenant_id == tenant_id, File.id == file_id)
        result = session.execute(query).scalar_one_or_none()
        if result is None:
            raise FileNotFoundByIdError(file_id)
        return result

    @staticmethod
    def _to_response(file_record: File) -> FileResponse:
        """Convert a File model to a FileResponse.

        Args:
            file_record: SQLAlchemy File model instance.

        Returns:
            FileResponse schema.

        """
        return FileResponse(
            id=file_record.id,
            tenant_id=file_record.tenant_id,
            file_name=file_record.file_name,
            file_size=file_record.file_size,
            content_type=file_record.content_type,
            storage_path=file_record.storage_path,
            context_type=file_record.context_type,
            context_id=file_record.context_id,
            created_at=file_record.created_at,
            updated_at=file_record.updated_at,
            created_by=file_record.created_by,
            updated_by=file_record.updated_by,
        )
