"""Business logic handlers for notification operations."""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select, func, update, or_

from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.core.database.models import Notification
from unifiedui.caching.client import CacheClient

from unifiedui.schema.requests.notifications import CreateNotificationRequest
from unifiedui.schema.responses.notifications import (
    NotificationResponse,
    NotificationListResponse,
    UnreadCountResponse,
)
from unifiedui.logger import get_logger

logger = get_logger(__name__)


class NotificationHandler:
    """Handler class for notification business logic."""

    def __init__(
        self,
        db_client: SQLAlchemyClient,
        cache_client: Optional[CacheClient] = None,
    ):
        """Initialize the notification handler.

        Args:
            db_client: Database client for queries.
            cache_client: Optional cache client.
        """
        self.db_client = db_client
        self.cache_client = cache_client

    def _notification_to_response(self, notification: Notification) -> NotificationResponse:
        """Convert a Notification model to response schema.

        Args:
            notification: Notification ORM instance.

        Returns:
            NotificationResponse schema.
        """
        return NotificationResponse(
            id=notification.id,
            tenant_id=notification.tenant_id,
            user_id=notification.user_id,
            type=notification.type,
            title=notification.title,
            message=notification.message,
            resource_type=notification.resource_type,
            resource_id=notification.resource_id,
            is_read=notification.is_read,
            created_at=notification.created_at,
            updated_at=notification.updated_at,
        )

    def list_notifications(
        self,
        tenant_id: str,
        user_id: str,
        is_read: Optional[bool] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> NotificationListResponse:
        """List notifications for a user in a tenant.

        Args:
            tenant_id: Tenant ID for scoping.
            user_id: User ID to get notifications for.
            is_read: Filter by read status (None = all).
            limit: Maximum results to return.
            offset: Number of results to skip.

        Returns:
            NotificationListResponse with notifications and total count.
        """
        with self.db_client.get_session() as session:
            base_filter = [
                Notification.tenant_id == tenant_id,
                or_(
                    Notification.user_id == user_id,
                    Notification.user_id.is_(None),
                ),
            ]

            if is_read is not None:
                base_filter.append(Notification.is_read == is_read)

            count_query = select(func.count(Notification.id)).where(*base_filter)
            total = session.execute(count_query).scalar() or 0

            list_query = (
                select(Notification)
                .where(*base_filter)
                .order_by(Notification.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            notifications = session.execute(list_query).scalars().all()

            return NotificationListResponse(
                notifications=[self._notification_to_response(n) for n in notifications],
                total=total,
            )

    def get_unread_count(
        self,
        tenant_id: str,
        user_id: str,
    ) -> UnreadCountResponse:
        """Get unread notification count for polling.

        Args:
            tenant_id: Tenant ID for scoping.
            user_id: User ID to count unread for.

        Returns:
            UnreadCountResponse with count.
        """
        with self.db_client.get_session() as session:
            count_query = select(func.count(Notification.id)).where(
                Notification.tenant_id == tenant_id,
                or_(
                    Notification.user_id == user_id,
                    Notification.user_id.is_(None),
                ),
                Notification.is_read.is_(False),
            )
            count = session.execute(count_query).scalar() or 0
            return UnreadCountResponse(unread_count=count)

    def mark_as_read(
        self,
        tenant_id: str,
        notification_id: str,
        user_id: str,
    ) -> NotificationResponse:
        """Mark a single notification as read.

        Args:
            tenant_id: Tenant ID for scoping.
            notification_id: Notification ID to mark.
            user_id: User ID performing the action.

        Returns:
            Updated NotificationResponse.

        Raises:
            ValueError: If notification not found.
        """
        with self.db_client.get_session() as session:
            notification = session.execute(
                select(Notification).where(
                    Notification.id == notification_id,
                    Notification.tenant_id == tenant_id,
                    or_(
                        Notification.user_id == user_id,
                        Notification.user_id.is_(None),
                    ),
                )
            ).scalar_one_or_none()

            if not notification:
                raise ValueError(f"Notification {notification_id} not found")

            notification.is_read = True
            session.commit()
            session.refresh(notification)
            return self._notification_to_response(notification)

    def mark_all_as_read(
        self,
        tenant_id: str,
        user_id: str,
    ) -> int:
        """Mark all notifications as read for a user.

        Args:
            tenant_id: Tenant ID for scoping.
            user_id: User ID performing the action.

        Returns:
            Number of notifications marked as read.
        """
        with self.db_client.get_session() as session:
            stmt = (
                update(Notification)
                .where(
                    Notification.tenant_id == tenant_id,
                    or_(
                        Notification.user_id == user_id,
                        Notification.user_id.is_(None),
                    ),
                    Notification.is_read.is_(False),
                )
                .values(is_read=True)
            )
            result = session.execute(stmt)
            session.commit()
            return result.rowcount

    def delete_notification(
        self,
        tenant_id: str,
        notification_id: str,
        user_id: str,
    ) -> None:
        """Delete a notification.

        Args:
            tenant_id: Tenant ID for scoping.
            notification_id: Notification ID to delete.
            user_id: User ID performing the action.

        Raises:
            ValueError: If notification not found.
        """
        with self.db_client.get_session() as session:
            notification = session.execute(
                select(Notification).where(
                    Notification.id == notification_id,
                    Notification.tenant_id == tenant_id,
                    or_(
                        Notification.user_id == user_id,
                        Notification.user_id.is_(None),
                    ),
                )
            ).scalar_one_or_none()

            if not notification:
                raise ValueError(f"Notification {notification_id} not found")

            session.delete(notification)
            session.commit()

    def create_notification(
        self,
        request: CreateNotificationRequest,
    ) -> NotificationResponse:
        """Create a notification (internal webhook endpoint).

        Args:
            request: Notification creation request.

        Returns:
            Created NotificationResponse.
        """
        with self.db_client.get_session() as session:
            notification = Notification(
                id=str(uuid.uuid4()),
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                type=request.type,
                title=request.title,
                message=request.message,
                resource_type=request.resource_type,
                resource_id=request.resource_id,
                is_read=False,
            )
            session.add(notification)
            session.commit()
            session.refresh(notification)
            return self._notification_to_response(notification)
