"""Business logic handlers for recent visit operations."""

from __future__ import annotations

import uuid as uuid_mod
from typing import TYPE_CHECKING

from sqlalchemy import delete, func, select

from unifiedui.core.database.models import RecentVisit, utc_now
from unifiedui.logger import get_logger
from unifiedui.schema.responses.recent_visits import (
    RecentVisitListResponse,
    RecentVisitResponse,
)

if TYPE_CHECKING:
    from unifiedui.caching.client import CacheClient
    from unifiedui.core.database.client import SQLAlchemyClient
    from unifiedui.schema.requests.recent_visits import SyncRecentVisitsRequest

logger = get_logger(__name__)

MAX_VISITS_PER_USER = 50


class RecentVisitsHandler:
    """Handler class for recent visit business logic."""

    def __init__(
        self,
        db_client: SQLAlchemyClient,
        cache_client: CacheClient | None = None,
    ):
        """Initialize the recent visits handler.

        Args:
            db_client: Database client for queries.
            cache_client: Optional cache client.
        """
        self.db_client = db_client
        self.cache_client = cache_client

    def _visit_to_response(self, visit: RecentVisit) -> RecentVisitResponse:
        """Convert a RecentVisit model to response schema.

        Args:
            visit: RecentVisit ORM instance.

        Returns:
            RecentVisitResponse schema.
        """
        return RecentVisitResponse(
            id=visit.id,
            tenant_id=visit.tenant_id,
            user_id=visit.user_id,
            resource_type=visit.resource_type,
            resource_id=visit.resource_id,
            resource_name=visit.resource_name,
            visited_at=visit.visited_at,
        )

    def list_recent_visits(
        self,
        tenant_id: str,
        user_id: str,
        limit: int = 20,
    ) -> RecentVisitListResponse:
        """List recent visits for a user.

        Args:
            tenant_id: Tenant ID for scoping.
            user_id: User ID to get visits for.
            limit: Maximum results to return.

        Returns:
            RecentVisitListResponse with visits and total count.
        """
        with self.db_client.get_session() as session:
            count_query = select(func.count(RecentVisit.id)).where(
                RecentVisit.tenant_id == tenant_id,
                RecentVisit.user_id == user_id,
            )
            total = session.execute(count_query).scalar() or 0

            list_query = (
                select(RecentVisit)
                .where(
                    RecentVisit.tenant_id == tenant_id,
                    RecentVisit.user_id == user_id,
                )
                .order_by(RecentVisit.visited_at.desc())
                .limit(limit)
            )
            visits = session.execute(list_query).scalars().all()

            return RecentVisitListResponse(
                visits=[self._visit_to_response(v) for v in visits],
                total=total,
            )

    def _cleanup_old_visits(
        self,
        session,
        tenant_id: str,
        user_id: str,
    ) -> None:
        """Remove oldest visits if user exceeds MAX_VISITS_PER_USER.

        Args:
            session: Database session.
            tenant_id: Tenant scope.
            user_id: User scope.
        """
        count_query = select(func.count(RecentVisit.id)).where(
            RecentVisit.tenant_id == tenant_id,
            RecentVisit.user_id == user_id,
        )
        count = session.execute(count_query).scalar() or 0

        if count > MAX_VISITS_PER_USER:
            excess = count - MAX_VISITS_PER_USER
            oldest_ids_query = (
                select(RecentVisit.id)
                .where(
                    RecentVisit.tenant_id == tenant_id,
                    RecentVisit.user_id == user_id,
                )
                .order_by(RecentVisit.visited_at.asc())
                .limit(excess)
            )
            oldest_ids = [row[0] for row in session.execute(oldest_ids_query).all()]
            if oldest_ids:
                session.execute(delete(RecentVisit).where(RecentVisit.id.in_(oldest_ids)))

    def sync_recent_visits(
        self,
        tenant_id: str,
        user_id: str,
        request: SyncRecentVisitsRequest,
    ) -> RecentVisitListResponse:
        """Batch-sync recent visits from frontend localStorage.

        Uses upsert logic: if visit exists, update visited_at and resource_name.
        If not, create new. Then cleanup to MAX_VISITS_PER_USER.

        Args:
            tenant_id: Tenant ID for scoping.
            user_id: User ID syncing visits.
            request: Sync request with list of visits.

        Returns:
            Updated RecentVisitListResponse.
        """
        with self.db_client.get_session() as session:
            for visit_item in request.visits:
                existing = session.execute(
                    select(RecentVisit).where(
                        RecentVisit.tenant_id == tenant_id,
                        RecentVisit.user_id == user_id,
                        RecentVisit.resource_type == visit_item.resource_type,
                        RecentVisit.resource_id == visit_item.resource_id,
                    )
                ).scalar_one_or_none()

                if existing:
                    existing.visited_at = utc_now()
                    existing.resource_name = visit_item.resource_name
                else:
                    new_visit = RecentVisit(
                        id=str(uuid_mod.uuid4()),
                        tenant_id=tenant_id,
                        user_id=user_id,
                        resource_type=visit_item.resource_type,
                        resource_id=visit_item.resource_id,
                        resource_name=visit_item.resource_name,
                    )
                    session.add(new_visit)

            session.commit()
            self._cleanup_old_visits(session, tenant_id, user_id)
            session.commit()

        return self.list_recent_visits(tenant_id, user_id, limit=20)
