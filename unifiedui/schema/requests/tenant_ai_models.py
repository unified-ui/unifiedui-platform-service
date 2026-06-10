"""Request schemas for tenant AI models."""

from pydantic import BaseModel, Field

from unifiedui.core.database.enums import AIModelProviderEnum, AIModelPurposeGroupEnum, AIModelTypeEnum


class CreateTenantAIModelRequest(BaseModel):
    """Request model for creating a tenant AI model."""

    name: str = Field(..., min_length=1, max_length=255, description="AI model display name")
    description: str | None = Field(None, max_length=2000, description="AI model description")
    type: AIModelTypeEnum = Field(..., description="Model type (LLM_MODEL or EMBEDDING_MODEL)")
    provider: AIModelProviderEnum = Field(..., description="AI model provider")
    purpose_groups: list[AIModelPurposeGroupEnum] = Field(
        default_factory=list, description="Purpose groups this model serves"
    )
    config: dict = Field(default_factory=dict, description="Provider-specific configuration")
    credential_id: str | None = Field(None, description="Optional credential ID for API key")
    priority: int = Field(0, ge=0, description="Priority for load-balancing (0 = highest)")


class UpdateTenantAIModelRequest(BaseModel):
    """Request model for updating a tenant AI model."""

    name: str | None = Field(None, min_length=1, max_length=255, description="AI model display name")
    description: str | None = Field(None, max_length=2000, description="AI model description")
    purpose_groups: list[AIModelPurposeGroupEnum] | None = Field(None, description="Purpose groups this model serves")
    config: dict | None = Field(None, description="Provider-specific configuration")
    credential_id: str | None = Field(None, description="Optional credential ID for API key")
    priority: int | None = Field(None, ge=0, description="Priority for load-balancing")
