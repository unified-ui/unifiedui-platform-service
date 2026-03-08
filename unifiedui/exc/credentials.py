"""Custom exception for credentials."""


class CredentialNotFoundError(Exception):
    """Exception raised when a credential is not found."""

    def __init__(self, credential_id: str):
        self.credential_id = credential_id
        super().__init__(f"Credential with ID '{credential_id}' not found")
