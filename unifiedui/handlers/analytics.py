"""Aggregation handler: builds analytics responses from message_metric/feedback."""

import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, select

from unifiedui.core.caching.client import BaseCacheClient
from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.core.database.models import MessageFeedback, MessageMetric
from unifiedui.schema.responses.analytics import (
    AgentPerformanceEntry,
    AnalyticsKPIs,
    ChatAgentAnalyticsResponse,
    ExecutionSeriesPoint,
    FeedbackBreakdownEntry,
    TokenSeriesPoint,
    TopAgent,
    WorkflowAnalyticsResponse,
    WorkflowExecutionEntry,
)


class AnalyticsHandler:
    """Handler producing aggregated analytics views over MessageMetric/MessageFeedback."""

    def __init__(
        self,
        db_client: SQLAlchemyClient,
        cache_client: BaseCacheClient | None = None,
        cache_ttl_seconds: int = 60,
    ) -> None:
        """Initialize the handler.

        Args:
            db_client: SQLAlchemy database client.
            cache_client: Optional cache client for response caching.
            cache_ttl_seconds: TTL in seconds for cached analytics responses.
        """
        self.db_client = db_client
        self.cache_client = cache_client
        self.cache_ttl_seconds = cache_ttl_seconds

    def _cache_key(self, prefix: str, **kwargs: object) -> str:
        """Build a deterministic cache key from kwargs."""
        payload = json.dumps(kwargs, default=str, sort_keys=True)
        digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
        return f"analytics:{prefix}:{digest}"

    def _cache_get(self, key: str) -> dict | None:
        """Best-effort cache read; swallows errors."""
        if self.cache_client is None:
            return None
        try:
            value = self.cache_client.get(key)
            return value if isinstance(value, dict) else None
        except Exception:
            return None

    def _cache_set(self, key: str, value: dict) -> None:
        """Best-effort cache write; swallows errors."""
        if self.cache_client is None:
            return
        try:
            self.cache_client.set(key, value, ttl=self.cache_ttl_seconds)
        except Exception:
            pass

    @staticmethod
    def _default_window() -> tuple[datetime, datetime]:
        """Return a sensible default time window (last 30 days)."""
        end = datetime.now(UTC)
        return end - timedelta(days=30), end

    def chat_agent_analytics(
        self,
        tenant_id: str,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
        agent_ids: list[str] | None = None,
    ) -> ChatAgentAnalyticsResponse:
        """Compute analytics over chat-agent message metrics."""
        start, end = (from_dt, to_dt) if from_dt and to_dt else self._default_window()
        cache_key = self._cache_key(
            "chat_agent",
            tenant_id=tenant_id,
            start=start.isoformat(),
            end=end.isoformat(),
            agent_ids=sorted(agent_ids) if agent_ids else None,
        )
        cached = self._cache_get(cache_key)
        if cached is not None:
            return ChatAgentAnalyticsResponse.model_validate(cached)
        with self.db_client.get_session() as session:
            base_filters = [
                MessageMetric.tenant_id == tenant_id,
                MessageMetric.created_at >= start,
                MessageMetric.created_at <= end,
                MessageMetric.chat_agent_id.is_not(None),
            ]
            if agent_ids:
                base_filters.append(MessageMetric.chat_agent_id.in_(agent_ids))

            stmt = select(MessageMetric).where(and_(*base_filters))
            metrics = list(session.execute(stmt).scalars().all())

            kpis = self._compute_kpis(metrics, tenant_id, session, message_ids=[m.message_id for m in metrics])
            series = self._compute_token_series(metrics)
            top_agents = self._compute_top_agents(metrics)
            performance = self._compute_performance(metrics)
            feedback = self._compute_feedback_breakdown(session, tenant_id, [m.message_id for m in metrics])

            response = ChatAgentAnalyticsResponse(
                kpis=kpis,
                token_series=series,
                top_agents_by_tokens=top_agents,
                feedback_breakdown=feedback,
                performance=performance,
            )
            self._cache_set(cache_key, response.model_dump(mode="json"))
            return response

    def workflow_analytics(
        self,
        tenant_id: str,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
        workflow_ids: list[str] | None = None,
    ) -> WorkflowAnalyticsResponse:
        """Compute analytics over workflow message metrics."""
        start, end = (from_dt, to_dt) if from_dt and to_dt else self._default_window()
        cache_key = self._cache_key(
            "workflow",
            tenant_id=tenant_id,
            start=start.isoformat(),
            end=end.isoformat(),
            workflow_ids=sorted(workflow_ids) if workflow_ids else None,
        )
        cached = self._cache_get(cache_key)
        if cached is not None:
            return WorkflowAnalyticsResponse.model_validate(cached)
        with self.db_client.get_session() as session:
            base_filters = [
                MessageMetric.tenant_id == tenant_id,
                MessageMetric.created_at >= start,
                MessageMetric.created_at <= end,
                MessageMetric.workflow_id.is_not(None),
            ]
            if workflow_ids:
                base_filters.append(MessageMetric.workflow_id.in_(workflow_ids))

            stmt = select(MessageMetric).where(and_(*base_filters))
            metrics = list(session.execute(stmt).scalars().all())

            kpis = self._compute_kpis(metrics, tenant_id, session, message_ids=[m.message_id for m in metrics])

            total_exec = len(metrics)
            success = sum(1 for m in metrics if m.status == "SUCCESS")
            success_rate = success / total_exec if total_exec else 0.0
            durations = [m.latency_ms / 1000.0 for m in metrics if m.latency_ms is not None]
            avg_duration_s = sum(durations) / len(durations) if durations else 0.0

            token_series = self._compute_token_series(metrics)
            exec_series = self._compute_execution_series(metrics)
            recent = self._compute_recent_executions(metrics)

            response = WorkflowAnalyticsResponse(
                kpis=kpis,
                total_executions=total_exec,
                success_rate=success_rate,
                avg_duration_s=avg_duration_s,
                token_series=token_series,
                executions_series=exec_series,
                recent_executions=recent,
            )
            self._cache_set(cache_key, response.model_dump(mode="json"))
            return response

    def _compute_kpis(
        self, metrics: list[MessageMetric], tenant_id: str, session, message_ids: list[str]
    ) -> AnalyticsKPIs:
        total = len(metrics)
        tin = sum(m.tokens_input or 0 for m in metrics)
        tout = sum(m.tokens_output or 0 for m in metrics)
        latencies = [m.latency_ms for m in metrics if m.latency_ms is not None]
        avg_lat = sum(latencies) / len(latencies) if latencies else 0.0
        errors = sum(1 for m in metrics if m.status == "FAILED")
        error_rate = errors / total if total else 0.0
        feedback_score = self._compute_feedback_score(session, tenant_id, message_ids)
        return AnalyticsKPIs(
            total_messages=total,
            total_tokens_input=tin,
            total_tokens_output=tout,
            avg_latency_ms=avg_lat,
            feedback_score=feedback_score,
            error_rate=error_rate,
        )

    @staticmethod
    def _compute_feedback_score(session, tenant_id: str, message_ids: list[str]) -> float:
        if not message_ids:
            return 0.0
        rating_col = MessageFeedback.rating
        stmt = (
            select(rating_col, func.count())
            .where(
                MessageFeedback.tenant_id == tenant_id,
                MessageFeedback.message_id.in_(message_ids),
            )
            .group_by(rating_col)
        )
        rows = session.execute(stmt).all()
        ups = sum(c for r, c in rows if r == "THUMBS_UP")
        downs = sum(c for r, c in rows if r == "THUMBS_DOWN")
        total = ups + downs
        return ups / total if total else 0.0

    @staticmethod
    def _compute_token_series(metrics: list[MessageMetric]) -> list[TokenSeriesPoint]:
        bucket: dict[str, dict[str, int]] = defaultdict(lambda: {"in": 0, "out": 0})
        for m in metrics:
            day = m.created_at.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            bucket[day]["in"] += m.tokens_input or 0
            bucket[day]["out"] += m.tokens_output or 0
        out: list[TokenSeriesPoint] = []
        for day_iso in sorted(bucket):
            out.append(
                TokenSeriesPoint(
                    date=datetime.fromisoformat(day_iso),
                    tokens_in=bucket[day_iso]["in"],
                    tokens_out=bucket[day_iso]["out"],
                )
            )
        return out

    @staticmethod
    def _compute_top_agents(metrics: list[MessageMetric]) -> list[TopAgent]:
        totals: Counter[str] = Counter()
        for m in metrics:
            if m.chat_agent_id:
                totals[m.chat_agent_id] += (m.tokens_input or 0) + (m.tokens_output or 0)
        return [TopAgent(agent_id=aid, total_tokens=tot) for aid, tot in totals.most_common(10)]

    @staticmethod
    def _compute_performance(metrics: list[MessageMetric]) -> list[AgentPerformanceEntry]:
        per_agent: dict[str, list[MessageMetric]] = defaultdict(list)
        for m in metrics:
            if m.chat_agent_id:
                per_agent[m.chat_agent_id].append(m)
        out: list[AgentPerformanceEntry] = []
        for aid, ms in per_agent.items():
            lat = [m.latency_ms for m in ms if m.latency_ms is not None]
            avg_lat = sum(lat) / len(lat) if lat else 0.0
            errors = sum(1 for m in ms if m.status == "FAILED")
            err_rate = errors / len(ms) if ms else 0.0
            out.append(AgentPerformanceEntry(agent_id=aid, avg_latency=avg_lat, error_rate=err_rate))
        return out

    @staticmethod
    def _compute_feedback_breakdown(session, tenant_id: str, message_ids: list[str]) -> list[FeedbackBreakdownEntry]:
        if not message_ids:
            return []
        stmt = (
            select(MessageFeedback.rating, func.count())
            .where(
                MessageFeedback.tenant_id == tenant_id,
                MessageFeedback.message_id.in_(message_ids),
            )
            .group_by(MessageFeedback.rating)
        )
        rows = session.execute(stmt).all()
        return [FeedbackBreakdownEntry(rating=r, reasons=[], count=c) for r, c in rows]

    @staticmethod
    def _compute_execution_series(metrics: list[MessageMetric]) -> list[ExecutionSeriesPoint]:
        bucket: dict[str, int] = defaultdict(int)
        for m in metrics:
            day = m.created_at.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            bucket[day] += 1
        return [ExecutionSeriesPoint(date=datetime.fromisoformat(d), executions=c) for d, c in sorted(bucket.items())]

    @staticmethod
    def _compute_recent_executions(metrics: list[MessageMetric]) -> list[WorkflowExecutionEntry]:
        recent = sorted(metrics, key=lambda m: m.created_at, reverse=True)[:20]
        return [
            WorkflowExecutionEntry(
                workflow_id=m.workflow_id or "",
                message_id=m.message_id,
                status=m.status,
                latency_ms=m.latency_ms or 0,
                timestamp=m.created_at,
            )
            for m in recent
        ]
