"""Request schemas for tools."""

from pydantic import BaseModel, Field

from unifiedui.core.database.enums import ToolTypeEnum


class CreateToolRequest(BaseModel):
    """Request model for creating a tool."""

    name: str = Field(..., min_length=1, max_length=255, description="Tool name")
    description: str | None = Field(None, max_length=2000, description="Tool description")
    type: ToolTypeEnum = Field(..., description="Tool type (MCP_SERVER, OPENAPI_DEFINITION)")
    config: dict | None = Field(default_factory=dict, description="Tool configuration")
    credential_id: str | None = Field(None, description="Optional credential ID for authentication")
    is_active: bool = Field(False, description="Whether the tool is active")


class UpdateToolRequest(BaseModel):
    """Request model for updating a tool."""

    name: str | None = Field(None, min_length=1, max_length=255, description="Tool name")
    description: str | None = Field(None, max_length=2000, description="Tool description")
    type: ToolTypeEnum | None = Field(None, description="Tool type (MCP_SERVER, OPENAPI_DEFINITION)")
    config: dict | None = Field(None, description="Tool configuration")
    credential_id: str | None = Field(None, description="Optional credential ID for authentication")
    is_active: bool | None = Field(None, description="Whether the tool is active")
