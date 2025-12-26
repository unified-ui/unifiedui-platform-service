"""Custom exception for applications."""


class ApplicationNotFoundError(Exception):
    """Exception raised when an application is not found."""
    
    def __init__(self, application_id: str):
        self.application_id = application_id
        super().__init__(f"Application with ID '{application_id}' not found")
