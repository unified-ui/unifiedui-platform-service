"""Shared test helper functions for API integration tests.

Provides reusable helpers for common test setup operations like
creating tenants and managing tenant membership.
"""

from typing import Any

from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers
from unifiedui.core.database.enums import PrincipalTypeEnum

ENDPOINT_TENANTS = "/api/v1/platform-service/tenants"
PRINCIPAL_TYPE_USER = PrincipalTypeEnum.IDENTITY_USER.value


def create_tenant_for_user(
    test_client: TestClient,
    user_token: Any,
    tenant_name: str = "Test Tenant",
) -> str:
    """Create a tenant via API and return its ID.

    Args:
        test_client: The FastAPI test client.
        user_token: The user's auth token (has .get_id() method).
        tenant_name: Name for the new tenant.

    Returns:
        The created tenant's ID.
    """
    headers = create_auth_headers(user_token, use_cache=False)
    response = test_client.post(
        ENDPOINT_TENANTS,
        json={
            "name": tenant_name,
            "description": f"Tenant for {user_token.get_id()}",
        },
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


def add_user_to_tenant(
    test_client: TestClient,
    tenant_id: str,
    admin_headers: dict,  # type: ignore[type-arg]
    user_id: str,
    role: str = "READER",
) -> None:
    """Add a user to a tenant via API.

    Args:
        test_client: The FastAPI test client.
        tenant_id: The tenant to add the user to.
        admin_headers: Auth headers of a tenant admin.
        user_id: The user ID to add.
        role: The tenant role to assign (default: READER).
    """
    response = test_client.put(
        f"{ENDPOINT_TENANTS}/{tenant_id}/principals",
        json={
            "principal_id": user_id,
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": role,
        },
        headers=admin_headers,
    )
    assert response.status_code == status.HTTP_200_OK


def add_user_to_tenant_with_token(
    test_client: TestClient,
    creator_token: Any,
    tenant_id: str,
    user_id: str,
    role: str = "READER",
) -> None:
    """Add a user to a tenant via API using a token instead of headers.

    Convenience wrapper around add_user_to_tenant that builds headers
    from a token object.

    Args:
        test_client: The FastAPI test client.
        creator_token: The admin's auth token.
        tenant_id: The tenant to add the user to.
        user_id: The user ID to add.
        role: The tenant role to assign (default: READER).
    """
    headers = create_auth_headers(creator_token, use_cache=False)
    add_user_to_tenant(test_client, tenant_id, headers, user_id, role)
