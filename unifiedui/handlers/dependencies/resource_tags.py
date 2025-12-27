"""Dependency for ResourceTagsHandler."""
from unifiedui.handlers.dependencies.database import get_db_client
from unifiedui.handlers.dependencies.cache import get_cache_client
from unifiedui.handlers.resource_tags import ResourceTagsHandler


def get_resource_tags_handler() -> ResourceTagsHandler:
    """Get ResourceTagsHandler instance."""
    return ResourceTagsHandler(
        db_client=get_db_client(),
        cache_client=get_cache_client()
    )
