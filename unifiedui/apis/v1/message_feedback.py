"""API routes for message-level user feedback."""

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request, status

from unifiedui.core.middleware.apis.v1.auth import authenticate
from unifiedui.exc.conversations import ConversationNotFoundError
from unifiedui.exc.message_feedback import MessageFeedbackNotFoundError
from unifiedui.handlers.dependencies.message_feedback import get_message_feedback_handler
from unifiedui.handlers.message_feedback import MessageFeedbackHandler
from unifiedui.schema.requests.message_feedback import MessageFeedbackResponse, UpsertMessageFeedbackRequest

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser

router = APIRouter(prefix="/conversations")


@router.post(
    "/{conversation_id}/messages/{message_id}/feedback",
    response_model=MessageFeedbackResponse,
    summary="Upsert feedback for a message",
)
@authenticate()
async def upsert_message_feedback(
    request: Request,
    tenant_id: str,
    conversation_id: str,
    message_id: str,
    payload: UpsertMessageFeedbackRequest,
    handler: MessageFeedbackHandler = Depends(get_message_feedback_handler),
) -> MessageFeedbackResponse:
    """Create or update the calling user's feedback for the given message."""
    user: ContextIdentityUser = request.state.user
    try:
        return handler.upsert(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            message_id=message_id,
            user_id=user.identity.get_id(),
            request=payload,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{conversation_id}/messages/{message_id}/feedback",
    response_model=MessageFeedbackResponse,
    summary="Get the caller's feedback for a message",
)
@authenticate()
async def get_message_feedback(
    request: Request,
    tenant_id: str,
    conversation_id: str,
    message_id: str,
    handler: MessageFeedbackHandler = Depends(get_message_feedback_handler),
) -> MessageFeedbackResponse:
    """Return the feedback the calling user has left on the given message."""
    user: ContextIdentityUser = request.state.user
    try:
        return handler.get_for_user(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            message_id=message_id,
            user_id=user.identity.get_id(),
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MessageFeedbackNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete(
    "/{conversation_id}/messages/{message_id}/feedback",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete the caller's feedback for a message",
)
@authenticate()
async def delete_message_feedback(
    request: Request,
    tenant_id: str,
    conversation_id: str,
    message_id: str,
    handler: MessageFeedbackHandler = Depends(get_message_feedback_handler),
) -> None:
    """Delete the calling user's feedback entry for the given message."""
    user: ContextIdentityUser = request.state.user
    try:
        handler.delete(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            message_id=message_id,
            user_id=user.identity.get_id(),
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MessageFeedbackNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{conversation_id}/feedback",
    response_model=list[MessageFeedbackResponse],
    summary="List all feedback for a conversation",
)
@authenticate()
async def list_conversation_feedback(
    request: Request,
    tenant_id: str,
    conversation_id: str,
    handler: MessageFeedbackHandler = Depends(get_message_feedback_handler),
) -> list[MessageFeedbackResponse]:
    """List every feedback entry attached to messages in this conversation."""
    try:
        return handler.list_for_conversation(tenant_id=tenant_id, conversation_id=conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
