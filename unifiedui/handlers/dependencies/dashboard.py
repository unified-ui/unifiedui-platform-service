"""FastAPI dependencies for dashboard handler."""
from unifiedui.handlers.dashboard import DashboardHandler
from unifiedui.handlers.dependencies.database import get_db_client
from unifiedui.handlers.dependencies.cache import get_cache_client


def get_dashboard_handler() -> DashboardHandler:
    """Create and return a dashboard handler."""
    return DashboardHandler(
        db_client=get_db_client(),
        cache_client=get_cache_client(),
    )
