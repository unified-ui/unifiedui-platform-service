"""Pydantic response schemas for the admin analytics endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AnalyticsKPIs(BaseModel):
    """Top-level KPI block returned by the analytics endpoints."""

    total_messages: int
    total_tokens_input: int
    total_tokens_output: int
    avg_latency_ms: float
    feedback_score: float
    error_rate: float


class TokenSeriesPoint(BaseModel):
    """Single point in the token time-series."""

    date: datetime
    tokens_in: int
    tokens_out: int


class TopAgent(BaseModel):
    """Top-N entry by total tokens consumed."""

    agent_id: str
    name: str | None = None
    total_tokens: int


class FeedbackBreakdownEntry(BaseModel):
    """Aggregated feedback distribution."""

    rating: str
    reasons: list[str] = []
    count: int


class AgentPerformanceEntry(BaseModel):
    """Per-agent performance summary."""

    agent_id: str
    avg_latency: float
    error_rate: float


class ChatAgentAnalyticsResponse(BaseModel):
    """Aggregated analytics for chat-agent traffic."""

    model_config = ConfigDict(from_attributes=True)

    kpis: AnalyticsKPIs
    token_series: list[TokenSeriesPoint]
    top_agents_by_tokens: list[TopAgent]
    feedback_breakdown: list[FeedbackBreakdownEntry]
    performance: list[AgentPerformanceEntry]


class WorkflowExecutionEntry(BaseModel):
    """Recent workflow execution summary."""

    workflow_id: str
    message_id: str
    status: str
    latency_ms: int
    timestamp: datetime


class ExecutionSeriesPoint(BaseModel):
    """Single point in the workflow execution time-series."""

    date: datetime
    executions: int


class WorkflowAnalyticsResponse(BaseModel):
    """Aggregated analytics for workflow executions."""

    model_config = ConfigDict(from_attributes=True)

    kpis: AnalyticsKPIs
    total_executions: int
    success_rate: float
    avg_duration_s: float
    token_series: list[TokenSeriesPoint]
    executions_series: list[ExecutionSeriesPoint]
    recent_executions: list[WorkflowExecutionEntry]
