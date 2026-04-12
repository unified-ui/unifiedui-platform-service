"""Custom exceptions for authentication operations."""


class AuthError(Exception):
    """Base exception for authentication-related errors."""

    pass


class InvalidCredentialsError(AuthError):
    """Exception raised when username or password is invalid."""

    def __init__(self) -> None:
        super().__init__("Invalid username or password")


class LDAPConnectionError(AuthError):
    """Exception raised when LDAP server is unreachable."""

    def __init__(self, detail: str = "LDAP server connection failed") -> None:
        self.detail = detail
        super().__init__(detail)


class InvalidRefreshTokenError(AuthError):
    """Exception raised when a refresh token is invalid or expired."""

    def __init__(self) -> None:
        super().__init__("Invalid or expired refresh token")
