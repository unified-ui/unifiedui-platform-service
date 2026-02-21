"""FastAPI dependencies for user favorites handler."""

from unifiedui.handlers.dependencies.cache import get_cache_client
from unifiedui.handlers.dependencies.database import get_db_client
from unifiedui.handlers.user_favorites import UserFavoritesHandler


def get_user_favorites_handler() -> UserFavoritesHandler:
    """Get a UserFavoritesHandler instance with injected dependencies."""
    db_client = get_db_client()
    cache_client = get_cache_client()
    return UserFavoritesHandler(db_client=db_client, cache_client=cache_client)
