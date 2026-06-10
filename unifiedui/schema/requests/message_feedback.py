"""Pydantic schemas for message feedback requests."""

from pydantic import BaseModel, ConfigDict, Field

from unifiedui.core.database.enums import MessageFeedbackRatingEnum, MessageFeedbackReasonEnum


class UpsertMessageFeedbackRequest(BaseModel):
    """Request payload to create or update feedback for a message."""

    rating: MessageFeedbackRatingEnum
    reasons: list[MessageFeedbackReasonEnum] = Field(default_factory=list, max_length=10)
    comment: str | None = Field(default=None, max_length=4000)


class MessageFeedbackResponse(BaseModel):
    """Response schema for a single message feedback entry."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    conversation_id: str
    message_id: str
    user_id: str
    rating: str
    reasons: list[str]
    comment: str | None
