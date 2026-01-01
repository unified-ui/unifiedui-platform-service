"""Principal-related exceptions."""


class PrincipalError(Exception):
    """Base exception for principal errors."""
    pass


class PrincipalNotFoundError(PrincipalError):
    """Exception raised when a principal is not found."""
    
    def __init__(self, principal_id: str):
        self.principal_id = principal_id
        super().__init__(f"Principal not found: {principal_id}")
