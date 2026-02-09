"""API routes for notification endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from unifiedui.handlers.notifications import NotificationHandler
from unifiedui.handlers.dependencies.notifications import get_notification_handler
from unifiedui.core.middleware.apis.v1.auth import authenticate
from unifiedui.core.identity.users import ContextIdentityUser
from unifiedui.schema.requests.notifications import CreateNotificationRequest
from unifiedui.schema.responses.notifications import (
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from unifiedui.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/notifications")


@router.get("", response_model=NotificationListResponse)
@authenticate()
async def list_notifications(
    request: Request,
    tenant_id: str,
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    handler: NotificationHandler = Depends(get_notification_handler),
):
    """List notifications for the authenticated user."""
    try:
        user: ContextIdentityUser = request.state.user
        user_id = user.identity.get_id()
        return handler.list_notifications(
            tenant_id=tenant_id,
            user_id=user_id,
            is_read=is_read,
            limit=limit,
            offset=offset,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list notifications: {e}")
        raise HTTPException(status_code=500, detail="Failed to list notifications")


@router.get("/unread-count", response_model=UnreadCountResponse)
@authenticate()
async def get_unread_count(
    request: Request,
    tenant_id: str,
    handler: NotificationHandler = Depends(get_notification_handler),
):
    """Get unread notification count for polling."""
    try:
        user: ContextIdentityUser = request.state.user
        user_id = user.identity.get_id()
        return handler.get_unread_count(tenant_id=tenant_id, user_id=user_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get unread count: {e}")
        raise HTTPException(status_code=500, detail="Failed to get unread count")


@router.put("/{notification_id}/read", response_model=NotificationResponse)
@authenticate()
async def mark_notification_read(
    request: Request,
    tenant_id: str,
    notification_id: str,
    handler: NotificationHandler = Depends(get_notification_handler),
):
    """Mark a single notification as read."""
    try:
        user: ContextIdentityUser = request.state.user
        user_id = user.identity.get_id()
        return handler.mark_as_read(
            tenant_id=tenant_id,
            notification_id=notification_id,
            user_id=user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mark notification as read: {e}")
        raise HTTPException(status_code=500, detail="Failed to mark notification as read")


@router.put("/read-all", response_model=dict)
@authenticate()
async def mark_all_read(
    request: Request,
    tenant_id: str,
    handler: NotificationHandler = Depends(get_notification_handler),
):
    """Mark all notifications as read."""
    try:
        user: ContextIdentityUser = request.state.user
        user_id = user.identity.get_id()
        count = handler.mark_all_as_read(tenant_id=tenant_id, user_id=user_id)
        return {"marked_count": count}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mark all as read: {e}")
        raise HTTPException(status_code=500, detail="Failed to mark all as read")


@router.delete("/{notification_id}", status_code=204)
@authenticate()
async def delete_notification(
    request: Request,
    tenant_id: str,
    notification_id: str,
    handler: NotificationHandler = Depends(get_notification_handler),
):
    """Delete a notification."""
    try:
        user: ContextIdentityUser = request.state.user
        user_id = user.identity.get_id()
        handler.delete_notification(
            tenant_id=tenant_id,
            notification_id=notification_id,
            user_id=user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete notification: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete notification")


@router.post("", response_model=NotificationResponse, status_code=201)
async def create_notification_webhook(
    request_body: CreateNotificationRequest,
    handler: NotificationHandler = Depends(get_notification_handler),
):
    """Internal webhook to create a notification (called by Agent Service)."""
    try:
        return handler.create_notification(request=request_body)
    except Exception as e:
        logger.error(f"Failed to create notification: {e}")
        raise HTTPException(status_code=500, detail="Failed to create notification")
