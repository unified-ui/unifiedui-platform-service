"""Response schemas for files."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class FileResponse(BaseModel):
    """Single file metadata response."""

    id: str
    tenant_id: str
    file_name: str
    file_size: int
    content_type: str
    storage_path: str
    context_type: str
    context_id: str | None
    created_at: datetime
    updated_at: datetime
    created_by: str | None
    updated_by: str | None
