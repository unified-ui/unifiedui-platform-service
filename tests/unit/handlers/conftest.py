"""Shared fixtures for handler unit tests."""

import uuid

import pytest
from sqlalchemy.orm import Session

from unifiedui.core.database.models import Organization

TEST_HANDLER_ORG_ID = "handler-test-org-00000000"


@pytest.fixture(autouse=True)
def seed_test_organization(test_db_session: Session) -> str:
    """Seed a test organization so Tenant objects can reference it.

    Auto-used by all handler tests that depend on test_db_session.

    Returns:
        The test organization ID.
    """
    org = Organization(
        id=TEST_HANDLER_ORG_ID,
        name="Handler Test Organization",
        slug=f"handler-test-org-{uuid.uuid4().hex[:8]}",
        identity_provider="MOCK",
        identity_tenant_id="test-tenant-123",
        subscription_tier="free",
        is_active=True,
        created_by="system",
        updated_by="system",
    )
    test_db_session.add(org)
    test_db_session.flush()
    return TEST_HANDLER_ORG_ID
