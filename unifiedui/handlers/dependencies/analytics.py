"""Dependency injection for the AnalyticsHandler."""

from fastapi import Depends

from unifiedui.caching.dependencies import get_cache_client
from unifiedui.core.caching.client import BaseCacheClient
from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.handlers.analytics import AnalyticsHandler
from unifiedui.handlers.dependencies.database import get_db_client


def get_analytics_handler(
    db_client: SQLAlchemyClient = Depends(get_db_client),
    cache_client: BaseCacheClient = Depends(get_cache_client),
) -> AnalyticsHandler:
    """Return an AnalyticsHandler instance with cache support."""
    return AnalyticsHandler(db_client, cache_client=cache_client, cache_ttl_seconds=60)
