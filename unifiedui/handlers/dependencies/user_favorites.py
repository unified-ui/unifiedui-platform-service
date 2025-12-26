"""FastAPI dependencies for user favorites handler."""
from aihub.handlers.user_favorites import UserFavoritesHandler
from aihub.handlers.dependencies.database import get_db_client
from aihub.handlers.dependencies.cache import get_cache_client


def get_user_favorites_handler() -> UserFavoritesHandler:
    """Get a UserFavoritesHandler instance with injected dependencies."""
    db_client = get_db_client()
    cache_client = get_cache_client()
    return UserFavoritesHandler(db_client=db_client, cache_client=cache_client)
