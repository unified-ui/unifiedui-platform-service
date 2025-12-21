"""Sample data fixtures for testing."""
import pytest


@pytest.fixture
def sample_tenant_data() -> dict[str, str]:
    """Sample tenant data for testing."""
    return {
        "name": "Test Tenant",
        "description": "A test tenant"
    }


@pytest.fixture
def sample_update_tenant_data() -> dict[str, str]:
    """Sample tenant update data for testing."""
    return {
        "name": "Updated Test Tenant",
        "description": "An updated test tenant"
    }
