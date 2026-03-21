"""Custom exceptions for external apps."""


class ExternalAppNotFoundError(Exception):
    """Exception raised when an external app is not found."""

    def __init__(self, external_app_id: str):
        self.external_app_id = external_app_id
        super().__init__(f"External app with ID '{external_app_id}' not found")


class ExternalAppAlreadyExistsError(Exception):
    """Exception raised when an external app with the same name already exists."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"External app with name '{name}' already exists")
