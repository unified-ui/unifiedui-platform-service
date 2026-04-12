"""Business logic handlers for recent visit operations."""

from __future__ import annotations

import uuid as uuid_mod
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, func, select

from unifiedui.core.database.models import (
    ChatAgent,
    ChatWidget,
    ExternalApp,
    RecentVisit,
    Workflow,
    utc_now,
)
from unifiedui.logger import get_logger
from unifiedui.schema.responses.recent_visits import (
    RecentVisitListResponse,
    RecentVisitResponse,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from unifiedui.caching.client import CacheClient
    from unifiedui.core.database.client import SQLAlchemyClient
    from unifiedui.schema.requests.recent_visits import SyncRecentVisitsRequest

logger = get_logger(__name__)

MAX_VISITS_PER_USER = 50

RESOURCE_TYPE_TO_MODEL: dict[str, Any] = {
    "chat_agent": ChatAgent,
    "workflow": Workflow,
    "external_app": ExternalApp,
    "chat_widget": ChatWidget,
}


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
        resource_types: list[str] | None = None,
    ) -> RecentVisitListResponse:
        """List recent visits for a user, filtering out deleted resources.

        Args:
            tenant_id: Tenant ID for scoping.
            user_id: User ID to get visits for.
            limit: Maximum results to return.
            resource_types: Optional list of resource types to filter by.

        Returns:
            RecentVisitListResponse with visits and total count.
        """
        with self.db_client.get_session() as session:
            base_filters = [
                RecentVisit.tenant_id == tenant_id,
                RecentVisit.user_id == user_id,
            ]
            if resource_types:
                base_filters.append(RecentVisit.resource_type.in_(resource_types))

            list_query = (
                select(RecentVisit)
                .where(*base_filters)
                .order_by(RecentVisit.visited_at.desc())
                .limit(limit * 2)  # Fetch more to account for deleted resources
            )
            visits = list(session.execute(list_query).scalars().all())

            # Filter out visits where resource no longer exists
            valid_visits = self._filter_existing_resources(session, tenant_id, visits)

            # Apply limit after filtering
            valid_visits = valid_visits[:limit]

            return RecentVisitListResponse(
                visits=[self._visit_to_response(v) for v in valid_visits],
                total=len(valid_visits),
            )

    def _filter_existing_resources(
        self,
        session: Session,
        tenant_id: str,
        visits: list[RecentVisit],
    ) -> list[RecentVisit]:
        """Filter visits to only include resources that still exist.

        Args:
            session: Database session.
            tenant_id: Tenant ID for scoping.
            visits: List of recent visits to filter.

        Returns:
            Filtered list of visits with existing resources.
        """
        if not visits:
            return []

        # Group visits by resource_type
        visits_by_type: dict[str, list[RecentVisit]] = {}
        for visit in visits:
            visits_by_type.setdefault(visit.resource_type, []).append(visit)

        # Check existence for each resource type
        existing_ids: set[str] = set()
        for resource_type, type_visits in visits_by_type.items():
            model = RESOURCE_TYPE_TO_MODEL.get(resource_type)
            if not model:
                continue

            resource_ids = [v.resource_id for v in type_visits]
            existing_query = select(model.id).where(
                model.tenant_id == tenant_id,
                model.id.in_(resource_ids),
            )
            result = session.execute(existing_query).scalars().all()
            existing_ids.update(result)

        # Filter visits to only include existing resources
        return [v for v in visits if v.resource_id in existing_ids]

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

    def delete_visits_for_resource(
        self,
        tenant_id: str,
        resource_type: str,
        resource_id: str,
    ) -> None:
        """Delete all recent visits for a specific resource.

        Called when a resource is deleted to clean up visit history.

        Args:
            tenant_id: Tenant ID for scoping.
            resource_type: Type of the deleted resource.
            resource_id: ID of the deleted resource.
        """
        with self.db_client.get_session() as session:
            session.execute(
                delete(RecentVisit).where(
                    RecentVisit.tenant_id == tenant_id,
                    RecentVisit.resource_type == resource_type,
                    RecentVisit.resource_id == resource_id,
                )
            )
            session.commit()
            logger.debug(
                "Cleaned up recent visits for deleted %s %s",
                resource_type,
                resource_id,
            )
