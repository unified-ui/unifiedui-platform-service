"""Response schemas for feedback stats endpoints."""

from pydantic import BaseModel


class ReasonBreakdownEntry(BaseModel):
    """A single reason with its occurrence count."""

    reason: str
    count: int


class RecentFeedbackEntry(BaseModel):
    """A recent negative feedback entry."""

    message_id: str
    conversation_id: str
    chat_agent_id: str | None = None
    chat_agent_name: str | None = None
    rating: str
    reasons: list[str]
    comment: str | None
    created_at: str


class FeedbackTimelineEntry(BaseModel):
    """A single feedback event for timeline visualization."""

    created_at: str
    delta: int
    cumulative: int


class FeedbackStatsResponse(BaseModel):
    """Aggregated feedback statistics across the requested scope."""

    total_feedbacks: int
    thumbs_up: int
    thumbs_down: int
    score: float | None
    reason_breakdown: list[ReasonBreakdownEntry]
    recent_negative: list[RecentFeedbackEntry]
    timeline: list[FeedbackTimelineEntry]


class FeedbackStatsPerAgent(BaseModel):
    """Slim per-agent feedback summary used in the batch response."""

    chat_agent_id: str
    chat_agent_name: str | None
    total_feedbacks: int
    thumbs_up: int
    thumbs_down: int
    score: float | None


class FeedbackStatsBatchResponse(BaseModel):
    """Batch feedback stats containing both aggregate and per-agent breakdown."""

    aggregate: FeedbackStatsResponse
    per_agent: list[FeedbackStatsPerAgent]
