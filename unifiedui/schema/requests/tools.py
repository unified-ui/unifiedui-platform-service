"""Request schemas for tools."""
from typing import Optional
from pydantic import BaseModel, Field

from unifiedui.core.database.enums import ToolTypeEnum


class CreateToolRequest(BaseModel):
    """Request model for creating a tool."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Tool name")
    description: Optional[str] = Field(None, max_length=2000, description="Tool description")
    type: ToolTypeEnum = Field(..., description="Tool type (MCP_SERVER, OPENAPI_DEFINITION)")
    config: Optional[dict] = Field(default_factory=dict, description="Tool configuration")
    credential_id: Optional[str] = Field(None, description="Optional credential ID for authentication")
    is_active: bool = Field(False, description="Whether the tool is active")


class UpdateToolRequest(BaseModel):
    """Request model for updating a tool."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Tool name")
    description: Optional[str] = Field(None, max_length=2000, description="Tool description")
    type: Optional[ToolTypeEnum] = Field(None, description="Tool type (MCP_SERVER, OPENAPI_DEFINITION)")
    config: Optional[dict] = Field(None, description="Tool configuration")
    credential_id: Optional[str] = Field(None, description="Optional credential ID for authentication")
    is_active: Optional[bool] = Field(None, description="Whether the tool is active")
