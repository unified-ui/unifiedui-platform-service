"""Custom exceptions for external apps."""


class ExternalAppNotFoundError(Exception):
    """Exception raised when an external app is not found."""

    def __init__(self, external_app_id: str):
        self.external_app_id = external_app_id
        super().__init__(f"External app with ID '{external_app_id}' not found")
