"""Response schemas for tenant AI models."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from unifiedui.core.database.enums import AIModelProviderEnum, AIModelPurposeGroupEnum, AIModelTypeEnum
from unifiedui.schema.responses.tags import TagSummary


class TenantAIModelResponse(BaseModel):
    """Response model for a tenant AI model."""

    id: str = Field(..., description="AI model ID")
    tenant_id: str = Field(..., description="Tenant ID")
    name: str = Field(..., description="AI model display name")
    description: str | None = Field(None, description="AI model description")
    type: AIModelTypeEnum = Field(..., description="Model type")
    provider: AIModelProviderEnum = Field(..., description="AI model provider")
    purpose_groups: list[AIModelPurposeGroupEnum] = Field(default_factory=list, description="Purpose groups")
    config: dict = Field(default_factory=dict, description="Provider-specific configuration")
    credential_id: str | None = Field(None, description="Linked credential ID")
    priority: int = Field(..., description="Priority for load-balancing")
    is_active: bool = Field(..., description="Whether the model is active")
    tags: list[TagSummary] = Field(default_factory=list, description="Tags on the AI model")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: str | None = Field(None, description="Creator user ID")
    updated_by: str | None = Field(None, description="Last updater user ID")

    model_config = ConfigDict(from_attributes=True)


class AIModelWithSecretResponse(BaseModel):
    """Internal S2S response including decrypted credential for agent-service."""

    id: str = Field(..., description="AI model ID")
    type: AIModelTypeEnum = Field(..., description="Model type")
    provider: AIModelProviderEnum = Field(..., description="AI model provider")
    config: dict = Field(default_factory=dict, description="Provider-specific configuration")
    credential_secret: dict | None = Field(None, description="Decrypted credential secret")
    priority: int = Field(..., description="Priority for load-balancing")

    model_config = ConfigDict(from_attributes=True)
