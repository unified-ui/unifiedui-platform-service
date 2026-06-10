"""Custom exceptions for message feedback."""


class MessageFeedbackNotFoundError(Exception):
    """Raised when a feedback entry is not found for the given message + user."""

    def __init__(self, message_id: str, user_id: str):
        self.message_id = message_id
        self.user_id = user_id
        super().__init__(f"Feedback for message '{message_id}' by user '{user_id}' not found")
