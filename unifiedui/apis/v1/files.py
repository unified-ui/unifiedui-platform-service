"""API routes for file management."""

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, status
from fastapi import File as FastAPIFile
from fastapi.responses import Response, StreamingResponse

from unifiedui.core.middleware.apis.v1.auth import authenticate
from unifiedui.exc.files import FileNotFoundByIdError, FileStorageNotConfiguredError, FileTooLargeError
from unifiedui.handlers.dependencies import get_file_handler
from unifiedui.handlers.files import FileHandler
from unifiedui.logger import get_logger
from unifiedui.schema.responses.files import FileResponse

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser

logger = get_logger(__name__)

router = APIRouter(prefix="/files")


@router.post(
    "",
    response_model=FileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload file",
    description="Upload a file to persistent storage.",
)
@authenticate()
async def upload_file(
    request: Request,
    tenant_id: str,
    file: UploadFile = FastAPIFile(..., description="File to upload"),
    context_type: str = Form(..., description="Context type (CHAT_ATTACHMENT or APP_IMAGE)"),
    context_id: str | None = Form(None, description="Related entity ID"),
    handler: FileHandler = Depends(get_file_handler),
) -> FileResponse:
    """Upload a file.

    Args:
        request: FastAPI request with user in state.
        tenant_id: Tenant ID from path.
        file: Uploaded file.
        context_type: Context type for the file.
        context_id: Optional related entity ID.
        handler: File handler dependency.

    Returns:
        Created file metadata.

    """
    try:
        user: ContextIdentityUser = request.state.user
        user_id = user.identity.get_id()

        file_name = file.filename or "unnamed"
        content_type = file.content_type or "application/octet-stream"
        file_size = file.size or 0

        logger.info(
            "API: Upload file",
            extra={"tenant_id": tenant_id, "user_id": user_id, "file_name": file_name},
        )

        return handler.upload_file(
            tenant_id=tenant_id,
            user_id=user_id,
            file_name=file_name,
            file_size=file_size,
            content_type=content_type,
            context_type=context_type,
            context_id=context_id,
            data=file.file,
        )
    except (FileTooLargeError, FileStorageNotConfiguredError):
        raise
    except Exception as e:
        logger.error("Failed to upload file: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to upload file")


@router.get(
    "/{file_id}",
    response_model=FileResponse,
    summary="Get file metadata",
    description="Get metadata for a specific file.",
)
@authenticate()
async def get_file_metadata(
    request: Request,
    tenant_id: str,
    file_id: str,
    handler: FileHandler = Depends(get_file_handler),
) -> FileResponse:
    """Get file metadata.

    Args:
        request: FastAPI request with user in state.
        tenant_id: Tenant ID from path.
        file_id: File ID from path.
        handler: File handler dependency.

    Returns:
        File metadata.

    """
    try:
        logger.info("API: Get file metadata", extra={"tenant_id": tenant_id, "file_id": file_id})
        return handler.get_file_metadata(tenant_id=tenant_id, file_id=file_id)
    except FileNotFoundByIdError:
        raise
    except Exception as e:
        logger.error("Failed to get file metadata: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get file metadata")


@router.get(
    "/{file_id}/download",
    summary="Download file",
    description="Download file content.",
)
@authenticate()
async def download_file(
    request: Request,
    tenant_id: str,
    file_id: str,
    handler: FileHandler = Depends(get_file_handler),
):
    """Download a file.

    Args:
        request: FastAPI request with user in state.
        tenant_id: Tenant ID from path.
        file_id: File ID from path.
        handler: File handler dependency.

    Returns:
        Streaming file response.

    """
    try:
        logger.info("API: Download file", extra={"tenant_id": tenant_id, "file_id": file_id})
        data, content_type, file_name = handler.download_file(tenant_id=tenant_id, file_id=file_id)
        return StreamingResponse(
            data,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{file_name}"',
                "Cache-Control": "private, max-age=600",
            },
        )
    except (FileNotFoundByIdError, FileStorageNotConfiguredError):
        raise
    except Exception as e:
        logger.error("Failed to download file: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to download file")


@router.delete(
    "/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete file",
    description="Delete a file. Requires ADMIN permission.",
)
@authenticate()
async def delete_file(
    request: Request,
    tenant_id: str,
    file_id: str,
    handler: FileHandler = Depends(get_file_handler),
) -> Response:
    """Delete a file.

    Args:
        request: FastAPI request with user in state.
        tenant_id: Tenant ID from path.
        file_id: File ID from path.
        handler: File handler dependency.

    Returns:
        No content (204).

    """
    try:
        user: ContextIdentityUser = request.state.user
        logger.info(
            "API: Delete file",
            extra={"tenant_id": tenant_id, "file_id": file_id, "user_id": user.identity.get_id()},
        )
        handler.delete_file(tenant_id=tenant_id, file_id=file_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except (FileNotFoundByIdError, FileStorageNotConfiguredError):
        raise
    except Exception as e:
        logger.error("Failed to delete file: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete file")
