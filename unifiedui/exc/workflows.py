"""Custom exception for workflows."""


class WorkflowNotFoundError(Exception):
    """Exception raised when a workflow is not found."""

    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        super().__init__(f"Workflow with ID '{workflow_id}' not found")


class WorkflowPermissionNotFoundError(Exception):
    """Exception raised when a workflow permission is not found."""

    def __init__(self, principal_id: str):
        self.principal_id = principal_id
        super().__init__(f"Permission for principal '{principal_id}' not found")


class WorkflowConfigValidationError(Exception):
    """Exception raised when workflow configuration validation fails."""

    def __init__(self, message: str, errors: list[str] | None = None):
        self.message = message
        self.errors = errors or []
        super().__init__(message)


class UnsupportedWorkflowTypeError(Exception):
    """Exception raised when an unsupported workflow type is used."""

    def __init__(self, workflow_type: str):
        self.workflow_type = workflow_type
        super().__init__(f"Unsupported workflow type: {workflow_type}")


class WorkflowKeyNotFoundError(Exception):
    """Exception raised when a workflow API key is not found."""

    def __init__(self, workflow_id: str, key_number: int):
        self.workflow_id = workflow_id
        self.key_number = key_number
        super().__init__(f"Key {key_number} not found for workflow '{workflow_id}'")


class WorkflowApiKeysNotAllowedError(Exception):
    """Exception raised when API key access is attempted but not allowed for this workflow."""

    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        super().__init__(
            f"API key authentication is not allowed for workflow '{workflow_id}'. Use Bearer token with a service principal instead."
        )
