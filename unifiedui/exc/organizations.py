"""Custom exceptions for organization operations."""


class OrganizationError(Exception):
    """Base exception for organization-related errors."""

    pass


class OrganizationNotFoundError(OrganizationError):
    """Exception raised when an organization is not found."""

    def __init__(self, organization_id: str):
        self.organization_id = organization_id
        super().__init__(f"Organization with ID '{organization_id}' not found")


class OrganizationAlreadyExistsError(OrganizationError):
    """Exception raised when trying to create an organization that already exists."""

    def __init__(self, identity_tenant_id: str):
        self.identity_tenant_id = identity_tenant_id
        super().__init__(
            f"Organization for identity tenant '{identity_tenant_id}' already exists"
        )


class OrganizationSlugAlreadyExistsError(OrganizationError):
    """Exception raised when organization slug already exists."""

    def __init__(self, slug: str):
        self.slug = slug
        super().__init__(f"Organization with slug '{slug}' already exists")


class OrganizationUpdateError(OrganizationError):
    """Exception raised when organization update fails."""

    def __init__(self, organization_id: str, reason: str):
        self.organization_id = organization_id
        self.reason = reason
        super().__init__(f"Failed to update organization '{organization_id}': {reason}")


class OrganizationMemberNotFoundError(OrganizationError):
    """Exception raised when an organization member is not found."""

    def __init__(self, member_id: str):
        self.member_id = member_id
        super().__init__(f"Organization member with ID '{member_id}' not found")


class OrganizationMemberAlreadyExistsError(OrganizationError):
    """Exception raised when a member already has the role in the organization."""

    def __init__(self, principal_id: str, role: str):
        self.principal_id = principal_id
        self.role = role
        super().__init__(
            f"Principal '{principal_id}' already has role '{role}' in organization"
        )


class OrganizationLimitExceededError(OrganizationError):
    """Exception raised when organization limits are exceeded."""

    def __init__(self, limit_type: str, current: int, maximum: int):
        self.limit_type = limit_type
        self.current = current
        self.maximum = maximum
        super().__init__(
            f"Organization {limit_type} limit exceeded: {current}/{maximum}"
        )


class TenantCannotBeDeletedError(OrganizationError):
    """Exception raised when trying to delete a non-deletable tenant."""

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        super().__init__(
            f"Tenant '{tenant_id}' cannot be deleted (is_default or can_be_deleted=false)"
        )
