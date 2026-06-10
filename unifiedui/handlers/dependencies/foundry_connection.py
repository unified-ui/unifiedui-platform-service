"""Foundry connection-tester dependency (REQ 008)."""

from fastapi import Depends

from unifiedui.handlers.credentials import CredentialHandler
from unifiedui.handlers.dependencies.credentials import get_credential_handler
from unifiedui.handlers.foundry_connection import FoundryConnectionTester


def get_foundry_connection_tester(
    credential_handler: CredentialHandler = Depends(get_credential_handler),
) -> FoundryConnectionTester:
    """Build a FoundryConnectionTester wired with the credential handler.

    Args:
        credential_handler: Credential lookup handler dependency.

    Returns:
        Configured FoundryConnectionTester.
    """
    return FoundryConnectionTester(credential_handler)
