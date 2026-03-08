"""Tests for ResourceCacheInvalidator utility."""

from unittest.mock import Mock

from unifiedui.handlers.cache_utils import ResourceCacheInvalidator


class TestResourceCacheInvalidator:
    """Test suite for ResourceCacheInvalidator."""

    def test_invalidate_list_with_cache_client(self) -> None:
        """Should call delete_pattern with correct list pattern."""
        mock_base_cache = Mock()
        mock_cache_client = Mock()
        mock_cache_client.client = mock_base_cache

        invalidator = ResourceCacheInvalidator(
            cache_client=mock_cache_client,
            prefix="chat_agents",
            resource_key="chat_agent",
        )

        invalidator.invalidate_list("tenant-123")

        mock_base_cache.delete_pattern.assert_called_once_with("chat_agents:list:tenant:tenant-123:*")

    def test_invalidate_list_without_cache_client(self) -> None:
        """Should not raise when cache_client is None."""
        invalidator = ResourceCacheInvalidator(
            cache_client=None,
            prefix="chat_agents",
            resource_key="chat_agent",
        )

        invalidator.invalidate_list("tenant-123")

    def test_invalidate_detail_with_cache_client(self) -> None:
        """Should call delete with correct detail key."""
        mock_base_cache = Mock()
        mock_cache_client = Mock()
        mock_cache_client.client = mock_base_cache

        invalidator = ResourceCacheInvalidator(
            cache_client=mock_cache_client,
            prefix="tools",
            resource_key="tool",
        )

        invalidator.invalidate_detail("tenant-123", "tool-456")

        mock_base_cache.delete.assert_called_once_with("tools:detail:tenant:tenant-123:tool:tool-456")

    def test_invalidate_detail_without_cache_client(self) -> None:
        """Should not raise when cache_client is None."""
        invalidator = ResourceCacheInvalidator(
            cache_client=None,
            prefix="tools",
            resource_key="tool",
        )

        invalidator.invalidate_detail("tenant-123", "tool-456")

    def test_invalidate_permissions_with_cache_client(self) -> None:
        """Should call delete_pattern with correct permissions pattern."""
        mock_base_cache = Mock()
        mock_cache_client = Mock()
        mock_cache_client.client = mock_base_cache

        invalidator = ResourceCacheInvalidator(
            cache_client=mock_cache_client,
            prefix="credentials",
            resource_key="cred",
        )

        invalidator.invalidate_permissions("tenant-123", "cred-789")

        mock_base_cache.delete_pattern.assert_called_once_with(
            "credentials:permissions:tenant:tenant-123:cred:cred-789:*"
        )

    def test_invalidate_permissions_without_cache_client(self) -> None:
        """Should not raise when cache_client is None."""
        invalidator = ResourceCacheInvalidator(
            cache_client=None,
            prefix="credentials",
            resource_key="cred",
        )

        invalidator.invalidate_permissions("tenant-123", "cred-789")

    def test_different_prefix_and_resource_key(self) -> None:
        """Should correctly use custom prefix and resource_key."""
        mock_base_cache = Mock()
        mock_cache_client = Mock()
        mock_cache_client.client = mock_base_cache

        invalidator = ResourceCacheInvalidator(
            cache_client=mock_cache_client,
            prefix="ai_models",
            resource_key="model",
        )

        invalidator.invalidate_list("t1")
        invalidator.invalidate_detail("t1", "m1")
        invalidator.invalidate_permissions("t1", "m1")

        mock_base_cache.delete_pattern.assert_any_call("ai_models:list:tenant:t1:*")
        mock_base_cache.delete.assert_called_once_with("ai_models:detail:tenant:t1:model:m1")
        mock_base_cache.delete_pattern.assert_any_call("ai_models:permissions:tenant:t1:model:m1:*")
