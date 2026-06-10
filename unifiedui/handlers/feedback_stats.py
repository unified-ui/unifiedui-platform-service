"""Handler for feedback statistics aggregation."""

from datetime import datetime

from sqlalchemy import case, func, select

from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.core.database.enums import MessageFeedbackRatingEnum
from unifiedui.core.database.models import ChatAgent, Conversation, MessageFeedback
from unifiedui.schema.responses.feedback_stats import (
    FeedbackStatsBatchResponse,
    FeedbackStatsPerAgent,
    FeedbackStatsResponse,
    FeedbackTimelineEntry,
    ReasonBreakdownEntry,
    RecentFeedbackEntry,
)


class FeedbackStatsHandler:
    """Handler class for feedback stats aggregation logic."""

    def __init__(self, db_client: SQLAlchemyClient) -> None:
        """Initialize the handler.

        Args:
            db_client: SQLAlchemy database client.
        """
        self.db_client = db_client

    def get_feedback_stats(
        self,
        tenant_id: str,
        chat_agent_ids: list[str] | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> FeedbackStatsBatchResponse:
        """Aggregate feedback statistics with optional filtering.

        Args:
            tenant_id: Tenant scope.
            chat_agent_ids: Optional list of chat agent IDs to scope to.
            from_date: Optional start date filter.
            to_date: Optional end date filter.

        Returns:
            Batch feedback stats response with overall aggregate and per-agent
            breakdown.
        """
        with self.db_client.get_session() as session:
            base_filter = [MessageFeedback.tenant_id == tenant_id]

            if chat_agent_ids:
                base_filter.append(
                    MessageFeedback.conversation_id.in_(
                        select(Conversation.id).where(
                            Conversation.tenant_id == tenant_id,
                            Conversation.chat_agent_id.in_(chat_agent_ids),
                        )
                    )
                )

            if from_date:
                base_filter.append(MessageFeedback.created_at >= from_date)
            if to_date:
                base_filter.append(MessageFeedback.created_at <= to_date)

            count_stmt = select(
                func.count(MessageFeedback.id).label("total"),
                func.sum(
                    case(
                        (MessageFeedback.rating == MessageFeedbackRatingEnum.THUMBS_UP, 1),
                        else_=0,
                    )
                ).label("thumbs_up"),
                func.sum(
                    case(
                        (MessageFeedback.rating == MessageFeedbackRatingEnum.THUMBS_DOWN, 1),
                        else_=0,
                    )
                ).label("thumbs_down"),
            ).where(*base_filter)

            row = session.execute(count_stmt).one()
            total = row.total or 0
            thumbs_up = row.thumbs_up or 0
            thumbs_down = row.thumbs_down or 0
            score = round(thumbs_up / total, 3) if total > 0 else None

            recent_stmt = (
                select(
                    MessageFeedback,
                    Conversation.chat_agent_id,
                    ChatAgent.name,
                )
                .outerjoin(Conversation, Conversation.id == MessageFeedback.conversation_id)
                .outerjoin(ChatAgent, ChatAgent.id == Conversation.chat_agent_id)
                .where(
                    *base_filter,
                    MessageFeedback.rating == MessageFeedbackRatingEnum.THUMBS_DOWN,
                )
                .order_by(MessageFeedback.created_at.desc())
                .limit(100)
            )
            recent_rows = session.execute(recent_stmt).all()

            recent_negative = [
                RecentFeedbackEntry(
                    message_id=fb.message_id,
                    conversation_id=fb.conversation_id,
                    chat_agent_id=agent_id,
                    chat_agent_name=agent_name,
                    rating=fb.rating,
                    reasons=fb.reasons if fb.reasons else [],
                    comment=fb.comment,
                    created_at=fb.created_at.isoformat(),
                )
                for fb, agent_id, agent_name in recent_rows
            ]

            reason_counts: dict[str, int] = {}
            for fb, _agent_id, _agent_name in recent_rows:
                if fb.reasons:
                    for reason in fb.reasons:
                        reason_counts[reason] = reason_counts.get(reason, 0) + 1

            if thumbs_down > 100:
                all_negative_stmt = select(MessageFeedback.reasons).where(
                    *base_filter,
                    MessageFeedback.rating == MessageFeedbackRatingEnum.THUMBS_DOWN,
                )
                all_negative = session.execute(all_negative_stmt).scalars().all()
                reason_counts = {}
                for reasons in all_negative:
                    if reasons:
                        for reason in reasons:
                            reason_counts[reason] = reason_counts.get(reason, 0) + 1

            reason_breakdown = sorted(
                [ReasonBreakdownEntry(reason=r, count=c) for r, c in reason_counts.items()],
                key=lambda x: x.count,
                reverse=True,
            )

            timeline_stmt = (
                select(MessageFeedback.created_at, MessageFeedback.rating)
                .where(*base_filter)
                .order_by(MessageFeedback.created_at.asc())
            )
            timeline_rows = session.execute(timeline_stmt).all()
            timeline: list[FeedbackTimelineEntry] = []
            cumulative = 0
            for created_at, rating in timeline_rows:
                delta = 1 if rating == MessageFeedbackRatingEnum.THUMBS_UP else -1
                cumulative += delta
                timeline.append(
                    FeedbackTimelineEntry(
                        created_at=created_at.isoformat(),
                        delta=delta,
                        cumulative=cumulative,
                    )
                )

            per_agent_stmt = (
                select(
                    Conversation.chat_agent_id.label("chat_agent_id"),
                    ChatAgent.name.label("chat_agent_name"),
                    func.count(MessageFeedback.id).label("total"),
                    func.sum(
                        case(
                            (MessageFeedback.rating == MessageFeedbackRatingEnum.THUMBS_UP, 1),
                            else_=0,
                        )
                    ).label("thumbs_up"),
                    func.sum(
                        case(
                            (MessageFeedback.rating == MessageFeedbackRatingEnum.THUMBS_DOWN, 1),
                            else_=0,
                        )
                    ).label("thumbs_down"),
                )
                .join(Conversation, Conversation.id == MessageFeedback.conversation_id)
                .outerjoin(ChatAgent, ChatAgent.id == Conversation.chat_agent_id)
                .where(*base_filter)
                .group_by(Conversation.chat_agent_id, ChatAgent.name)
            )
            per_agent_rows = session.execute(per_agent_stmt).all()
            per_agent: list[FeedbackStatsPerAgent] = []
            for agent_row in per_agent_rows:
                if agent_row.chat_agent_id is None:
                    continue
                agent_total = agent_row.total or 0
                agent_up = agent_row.thumbs_up or 0
                agent_down = agent_row.thumbs_down or 0
                rated = agent_up + agent_down
                agent_score = round(agent_up / rated, 3) if rated > 0 else None
                per_agent.append(
                    FeedbackStatsPerAgent(
                        chat_agent_id=str(agent_row.chat_agent_id),
                        chat_agent_name=agent_row.chat_agent_name,
                        total_feedbacks=agent_total,
                        thumbs_up=agent_up,
                        thumbs_down=agent_down,
                        score=agent_score,
                    )
                )

            aggregate = FeedbackStatsResponse(
                total_feedbacks=total,
                thumbs_up=thumbs_up,
                thumbs_down=thumbs_down,
                score=score,
                reason_breakdown=reason_breakdown,
                recent_negative=recent_negative,
                timeline=timeline,
            )
            return FeedbackStatsBatchResponse(aggregate=aggregate, per_agent=per_agent)
