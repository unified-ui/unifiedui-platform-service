"""Request schemas for external apps."""

from pydantic import BaseModel, Field


class CreateExternalAppRequest(BaseModel):
    """Request model for creating an external app."""

    name: str = Field(..., min_length=1, max_length=255, description="External app name")
    description: str | None = Field(None, max_length=2000, description="External app description")
    url: str = Field(..., min_length=1, max_length=2000, description="External app URL for iframe embedding")
    image_url: str | None = Field(None, max_length=2000, description="External app image URL")
    image_file_id: str | None = Field(None, max_length=36, description="File ID of uploaded app image")


class UpdateExternalAppRequest(BaseModel):
    """Request model for updating an external app."""

    name: str | None = Field(None, min_length=1, max_length=255, description="External app name")
    description: str | None = Field(None, max_length=2000, description="External app description")
    url: str | None = Field(None, min_length=1, max_length=2000, description="External app URL")
    image_url: str | None = Field(None, max_length=2000, description="External app image URL")
    image_file_id: str | None = Field(None, max_length=36, description="File ID of uploaded app image")
