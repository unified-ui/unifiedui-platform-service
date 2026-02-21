"""Custom group-related exceptions."""


class CustomGroupError(Exception):
    """Base exception for custom group errors."""

    pass


class CustomGroupNotFoundError(CustomGroupError):
    """Exception raised when a custom group is not found."""

    def __init__(self, group_id: str):
        self.group_id = group_id
        super().__init__(f"Custom group not found: {group_id}")


class CustomGroupAlreadyExistsError(CustomGroupError):
    """Exception raised when trying to create a group that already exists."""

    def __init__(self, tenant_id: str, name: str):
        self.tenant_id = tenant_id
        self.name = name
        super().__init__(f"Custom group '{name}' already exists in tenant {tenant_id}")
