"""Custom exceptions for tenant operations."""


class TenantError(Exception):
    """Base exception for tenant-related errors."""
    pass


class TenantNotFoundError(TenantError):
    """Exception raised when a tenant is not found."""
    
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        super().__init__(f"Tenant with ID '{tenant_id}' not found")


class TenantAlreadyExistsError(TenantError):
    """Exception raised when trying to create a tenant that already exists."""
    
    def __init__(self, tenant_name: str):
        self.tenant_name = tenant_name
        super().__init__(f"Tenant with name '{tenant_name}' already exists")


class TenantUpdateError(TenantError):
    """Exception raised when tenant update fails."""
    
    def __init__(self, tenant_id: str, reason: str):
        self.tenant_id = tenant_id
        self.reason = reason
        super().__init__(f"Failed to update tenant '{tenant_id}': {reason}")


class TenantDeleteError(TenantError):
    """Exception raised when tenant deletion fails."""
    
    def __init__(self, tenant_id: str, reason: str):
        self.tenant_id = tenant_id
        self.reason = reason
        super().__init__(f"Failed to delete tenant '{tenant_id}': {reason}")
