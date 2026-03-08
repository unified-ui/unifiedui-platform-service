"""Custom exception for chat widgets."""


class ChatWidgetNotFoundError(Exception):
    """Exception raised when a chat widget is not found."""

    def __init__(self, chat_widget_id: str):
        self.chat_widget_id = chat_widget_id
        super().__init__(f"Chat widget with ID '{chat_widget_id}' not found")
