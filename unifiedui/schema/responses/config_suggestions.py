"""Response schemas for config suggestions."""

from __future__ import annotations

from pydantic import BaseModel


class ConfigSuggestionsResponse(BaseModel):
    """Config suggestions grouped by field name."""

    suggestions: dict[str, list[str]]
