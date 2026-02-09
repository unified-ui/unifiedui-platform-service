"""Dependency injection for search handler."""
from unifiedui.handlers.search import SearchHandler
from unifiedui.handlers.dependencies import get_db_client, get_cache_client


def get_search_handler() -> SearchHandler:
    """Create and return a SearchHandler instance.

    Returns:
        SearchHandler with injected dependencies.
    """
    return SearchHandler(
        db_client=get_db_client(),
        cache_client=get_cache_client(),
    )
