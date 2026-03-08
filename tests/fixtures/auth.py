"""Authentication fixtures for testing."""

import logging
import uuid

import pytest

from unifiedui.identity.mock import MockIdentityToken

logger = logging.getLogger(__name__)


def create_test_user(
    user_id: str | None = None, name: str = "Test User", mail: str | None = None, idp_groups: list[str] | None = None
) -> MockIdentityToken:
    """
    Create a test user with JWT token.

    Args:
        user_id: User ID (if None, auto-generated from name + UUID)
        name: User's display name
        mail: User's email
        idp_groups: List of group IDs the user belongs to

    Returns:
        MockIdentityToken instance
    """
    # Generate unique user_id if not provided
    if user_id is None:
        user_id = f"test-{name.lower().replace(' ', '-')}-{str(uuid.uuid4())[:8]}"

    logger.info(f"Creating test user: user_id={user_id}, name={name}, mail={mail}, groups={idp_groups}")
    token = MockIdentityToken(user_id=user_id, name=name, mail=mail, idp_groups=idp_groups)
    logger.info(f"Generated JWT token: {token.get_token()[:50]}...")
    return token


def create_auth_headers(token: MockIdentityToken, use_cache: bool = True, **kwargs: str) -> dict[str, str]:
    """
    Create authentication headers for API requests.

    Args:
        token: MockIdentityToken instance
        use_cache: Whether to enable caching (default: True)
        **kwargs: Additional headers to include

    Returns:
        Dictionary with Authorization and optionally X-Use-Cache headers
    """
    headers = {"Authorization": f"Bearer {token.get_token()}", **kwargs}

    if not use_cache:
        headers["X-Use-Cache"] = "false"

    return headers


@pytest.fixture
def test_user_token() -> MockIdentityToken:
    """Create a default test user token."""
    logger.info("Creating default test user token")
    token = create_test_user(user_id="test-user-123")
    logger.info("Default test user token created")
    return token


@pytest.fixture
def auth_headers(test_user_token: MockIdentityToken) -> dict[str, str]:
    """Generate authentication headers for testing with real JWT."""
    logger.info("Generating auth headers")
    headers = {
        "Authorization": f"Bearer {test_user_token.get_token()}",
        "Content-Type": "application/json",
        "X-Use-Cache": "false",  # Disable caching in tests for consistency
    }
    logger.info(f"Auth headers: Authorization=Bearer {test_user_token.get_token()[:30]}...")
    return headers
