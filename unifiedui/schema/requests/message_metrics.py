"""Pydantic schemas for message metric ingestion."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from unifiedui.core.database.enums import MessageMetricStatusEnum


class MessageMetricCreateRequest(BaseModel):
    """Request payload for ingesting a single message metric."""

    model_config = ConfigDict(str_strip_whitespace=True)

    tenant_id: str
    message_id: str = Field(..., min_length=1, max_length=255)
    chat_agent_id: str | None = None
    workflow_id: str | None = None
    conversation_id: str | None = None
    user_id: str | None = None
    provider: str = Field(..., min_length=1, max_length=64)
    model: str = Field(..., min_length=1, max_length=128)
    tokens_input: int = Field(0, ge=0)
    tokens_output: int = Field(0, ge=0)
    latency_ms: int = Field(0, ge=0)
    agent_type: str = Field(..., min_length=1, max_length=64)
    status: MessageMetricStatusEnum
    error_code: str | None = Field(None, max_length=128)


class MessageMetricBatchRequest(BaseModel):
    """Bulk variant of MessageMetricCreateRequest (max 100 items per batch)."""

    items: list[MessageMetricCreateRequest] = Field(..., min_length=1, max_length=100)


class MessageMetricResponse(BaseModel):
    """Response payload representing a stored message metric."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    chat_agent_id: str | None
    workflow_id: str | None
    conversation_id: str | None
    message_id: str
    user_id: str | None
    provider: str
    model: str
    tokens_input: int
    tokens_output: int
    latency_ms: int
    agent_type: str
    status: str
    error_code: str | None
    created_at: datetime


class MessageMetricBatchResponse(BaseModel):
    """Bulk-ingest response with counts of inserts vs upserts."""

    inserted: int
    updated: int
