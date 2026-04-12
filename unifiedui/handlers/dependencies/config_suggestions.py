"""Dependency injection for config suggestions handler."""

from unifiedui.handlers.config_suggestions import ConfigSuggestionsHandler
from unifiedui.handlers.dependencies import get_db_client


def get_config_suggestions_handler() -> ConfigSuggestionsHandler:
    """Create and return a ConfigSuggestionsHandler instance.

    Returns:
        ConfigSuggestionsHandler with injected dependencies.
    """
    return ConfigSuggestionsHandler(
        db_client=get_db_client(),
    )
