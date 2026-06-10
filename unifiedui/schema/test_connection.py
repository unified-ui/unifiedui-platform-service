"""Schemas for chat agent connection testing (REQ 008)."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TestConnectionRequest(BaseModel):
    """Request model for testing a chat agent connection without persisting it.

    Used for the Foundry test-connection endpoint to verify auth and agent reachability
    during create/edit dialogs.
    """

    agent_type: str = Field(..., description="Foundry agent_type (AGENT or MULTI_AGENT)")
    api_version: str = Field(..., description="Foundry API version")
    project_endpoint: str = Field(..., description="Foundry project endpoint URL")
    agent_name: str = Field(..., description="Name/id of the agent in Foundry")
    auth_type: str = Field(
        ...,
        description="Authentication mode (ENTRA_ID_USER_TOKEN, ENTRA_ID_APP_REGISTRATION, API_KEY)",
    )
    credential_id: str | None = Field(default=None, description="Credential ID (required for non-user-token modes)")


class TestConnectionResponse(BaseModel):
    """Response model for test-connection result."""

    success: bool = Field(..., description="Whether the connection test succeeded")
    latency_ms: int = Field(..., description="HTTP round-trip latency in milliseconds")
    error_code: str | None = Field(
        default=None,
        description=("One of AUTH_FAILED, AGENT_NOT_FOUND, INVALID_ENDPOINT, TIMEOUT, CREDENTIAL_INVALID, UNKNOWN"),
    )
    error_message: str | None = Field(default=None, description="Human-readable error description")
    agent_metadata: dict[str, Any] | None = Field(default=None, description="Agent metadata returned by Foundry")

    model_config = ConfigDict(from_attributes=True)
