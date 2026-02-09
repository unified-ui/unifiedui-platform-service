"""Request schemas for ReACT agents."""
from typing import Optional, List
from pydantic import BaseModel, Field


class CreateReActAgentRequest(BaseModel):
    """Request model for creating a ReACT agent."""

    name: str = Field(..., min_length=1, max_length=255, description="ReACT agent name")
    description: Optional[str] = Field(None, max_length=2000, description="ReACT agent description")
    ai_model_ids: List[str] = Field(default_factory=list, description="List of AI model IDs to use")
    system_prompt: Optional[str] = Field(None, max_length=8000, description="System prompt for the agent")
    tool_ids: List[str] = Field(default_factory=list, description="List of tool IDs to attach")
    security_prompt: Optional[str] = Field(None, max_length=8000, description="Security prompt")
    tool_use_prompt: Optional[str] = Field(None, max_length=8000, description="Tool use instructions prompt")
    response_prompt: Optional[str] = Field(None, max_length=8000, description="Response formatting prompt")
    greeting_messages: List[str] = Field(default_factory=list, description="Greeting messages for the agent")
    config: Optional[dict] = Field(default_factory=dict, description="Agent configuration")
    is_active: bool = Field(False, description="Whether the agent is active")


class UpdateReActAgentRequest(BaseModel):
    """Request model for updating a ReACT agent."""

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="ReACT agent name")
    description: Optional[str] = Field(None, max_length=2000, description="ReACT agent description")
    ai_model_ids: Optional[List[str]] = Field(None, description="List of AI model IDs to use")
    system_prompt: Optional[str] = Field(None, max_length=8000, description="System prompt for the agent")
    tool_ids: Optional[List[str]] = Field(None, description="List of tool IDs to attach")
    security_prompt: Optional[str] = Field(None, max_length=8000, description="Security prompt")
    tool_use_prompt: Optional[str] = Field(None, max_length=8000, description="Tool use instructions prompt")
    response_prompt: Optional[str] = Field(None, max_length=8000, description="Response formatting prompt")
    greeting_messages: Optional[List[str]] = Field(None, description="Greeting messages for the agent")
    config: Optional[dict] = Field(None, description="Agent configuration")
    is_active: Optional[bool] = Field(None, description="Whether the agent is active")
