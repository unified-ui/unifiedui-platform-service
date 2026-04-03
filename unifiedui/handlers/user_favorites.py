"""Business logic handlers for user favorites operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import delete, select
from sqlalchemy.orm import joinedload

from unifiedui.core.database.models import (
    AutonomousAgent,
    AutonomousAgentUserFavorite,
    ChatAgent,
    ChatAgentUserFavorite,
    ChatWidget,
    ChatWidgetUserFavorite,
    Conversation,
    ConversationUserFavorite,
    ExternalApp,
    ExternalAppUserFavorite,
)
from unifiedui.logger import get_logger
from unifiedui.schema.responses.user_favorites import (
    UserFavoriteResponse,
    UserFavoritesListResponse,
    UserFavoritesUnifiedResponse,
    UserFavoriteWithNameResponse,
)

if TYPE_CHECKING:
    from unifiedui.caching.client import CacheClient
    from unifiedui.core.database.client import SQLAlchemyClient

logger = get_logger(__name__)


# Mapping of resource types to their models and ID fields
RESOURCE_FAVORITE_MAPPING: dict[str, dict[str, Any]] = {
    "chat-agents": {
        "model": ChatAgentUserFavorite,
        "id_field": "chat_agent_id",
        "relationship": "chat_agent",
        "resource_model": ChatAgent,
    },
    "autonomous-agents": {
        "model": AutonomousAgentUserFavorite,
        "id_field": "autonomous_agent_id",
        "relationship": "autonomous_agent",
        "resource_model": AutonomousAgent,
    },
    "chat-widgets": {
        "model": ChatWidgetUserFavorite,
        "id_field": "chat_widget_id",
        "relationship": "chat_widget",
        "resource_model": ChatWidget,
    },
    "conversations": {
        "model": ConversationUserFavorite,
        "id_field": "conversation_id",
        "relationship": "conversation",
        "resource_model": Conversation,
    },
    "external-apps": {
        "model": ExternalAppUserFavorite,
        "id_field": "external_app_id",
        "relationship": "external_app",
        "resource_model": ExternalApp,
    },
}


class UserFavoritesHandler:
    """Handler class for user favorites business logic."""

    def __init__(self, db_client: SQLAlchemyClient, cache_client: CacheClient | None = None):
        """
        Initialize the user favorites handler.

        Args:
            db_client: SQLAlchemy database client instance
            cache_client: Optional cache client for Redis caching
        """
        self.db_client = db_client
        self.cache_client = cache_client

    def list_user_favorites(
        self, tenant_id: str, user_id: str, resource_type: str, use_cache: bool = True
    ) -> UserFavoritesListResponse:
        """
        Get a list of user favorites for a specific resource type.

        Args:
            tenant_id: The ID of the tenant
            user_id: The ID of the user
            resource_type: Type of resource (chat-agents, autonomous-agents, etc.)
            use_cache: Whether to use caching

        Returns:
            List of user favorite responses
        """
        logger.info(
            "Listing user favorites", extra={"tenant_id": tenant_id, "user_id": user_id, "resource_type": resource_type}
        )

        mapping = RESOURCE_FAVORITE_MAPPING.get(resource_type)
        if not mapping:
            raise ValueError(f"Unknown resource type: {resource_type}")

        model: type[Any] = cast("type[Any]", mapping["model"])
        id_field: str = cast("str", mapping["id_field"])

        cache_key = f"user_favorites:{resource_type}:tenant:{tenant_id}:user:{user_id}"

        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug("Returning cached user favorites")
                    return UserFavoritesListResponse(
                        favorites=[UserFavoriteResponse(**item) for item in cached_data["favorites"]],
                        total=cached_data["total"],
                    )
            except Exception as e:
                logger.warning("Failed to get cached user favorites: %s", e)

        with self.db_client.get_session() as session:
            query = select(model).where(model.tenant_id == tenant_id, model.user_id == user_id)
            favorites = session.execute(query).scalars().all()

            logger.info("Retrieved user favorites", extra={"count": len(favorites)})

            favorite_responses = [
                UserFavoriteResponse(
                    tenant_id=fav.tenant_id,
                    user_id=fav.user_id,
                    resource_id=getattr(fav, id_field),
                    resource_type=resource_type,
                    created_at=fav.created_at,
                    updated_at=fav.updated_at,
                    created_by=fav.created_by,
                    updated_by=fav.updated_by,
                )
                for fav in favorites
            ]

            result = UserFavoritesListResponse(favorites=favorite_responses, total=len(favorite_responses))

            # Cache the result
            if use_cache and self.cache_client:
                try:
                    data = {"favorites": [f.model_dump() for f in favorite_responses], "total": result.total}
                    self.cache_client.client.set(cache_key, data, ttl=300)
                    logger.debug("Cached user favorites")
                except Exception as e:
                    logger.warning("Failed to cache user favorites: %s", e)

            return result

    def list_all_favorites_with_names(
        self, tenant_id: str, user_id: str, use_cache: bool = True
    ) -> UserFavoritesUnifiedResponse:
        """
        Get all user favorites across all resource types with resource names.

        Args:
            tenant_id: The ID of the tenant
            user_id: The ID of the user
            use_cache: Whether to use caching

        Returns:
            Unified list of all user favorites with resource names
        """
        logger.info(
            "Listing all user favorites with names",
            extra={"tenant_id": tenant_id, "user_id": user_id},
        )

        cache_key = f"user_favorites:all:tenant:{tenant_id}:user:{user_id}"

        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug("Returning cached unified user favorites")
                    return UserFavoritesUnifiedResponse(
                        favorites=[UserFavoriteWithNameResponse(**item) for item in cached_data["favorites"]]
                    )
            except Exception as e:
                logger.warning("Failed to get cached unified user favorites: %s", e)

        all_favorites: list[UserFavoriteWithNameResponse] = []

        with self.db_client.get_session() as session:
            for resource_type, mapping in RESOURCE_FAVORITE_MAPPING.items():
                model: type[Any] = cast("type[Any]", mapping["model"])
                id_field: str = cast("str", mapping["id_field"])
                relationship: str = cast("str", mapping["relationship"])

                # Query with eager loading of the relationship
                query = (
                    select(model)
                    .options(joinedload(getattr(model, relationship)))
                    .where(model.tenant_id == tenant_id, model.user_id == user_id)
                )
                favorites = session.execute(query).scalars().all()

                for fav in favorites:
                    resource = getattr(fav, relationship)
                    resource_name = getattr(resource, "name", None) if resource else None

                    # Handle Conversation which uses 'title' instead of 'name'
                    if resource_name is None and resource is not None:
                        resource_name = getattr(resource, "title", None)

                    all_favorites.append(
                        UserFavoriteWithNameResponse(
                            resource_id=getattr(fav, id_field),
                            resource_type=resource_type,
                            resource_name=resource_name or "Unknown",
                        )
                    )

        logger.info("Retrieved all user favorites with names", extra={"count": len(all_favorites)})

        result = UserFavoritesUnifiedResponse(favorites=all_favorites)

        # Cache the result
        if use_cache and self.cache_client:
            try:
                data = {"favorites": [f.model_dump() for f in all_favorites]}
                self.cache_client.client.set(cache_key, data, ttl=300)
                logger.debug("Cached unified user favorites")
            except Exception as e:
                logger.warning("Failed to cache unified user favorites: %s", e)

        return result

    def add_user_favorite(
        self, tenant_id: str, user_id: str, resource_type: str, resource_id: str
    ) -> UserFavoriteResponse:
        """
        Add a resource to user favorites.

        Args:
            tenant_id: The ID of the tenant
            user_id: The ID of the user
            resource_type: Type of resource (chat-agents, autonomous-agents, etc.)
            resource_id: The ID of the resource to favorite

        Returns:
            Created user favorite response
        """
        logger.info(
            "Adding user favorite",
            extra={
                "tenant_id": tenant_id,
                "user_id": user_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
            },
        )

        mapping = RESOURCE_FAVORITE_MAPPING.get(resource_type)
        if not mapping:
            raise ValueError(f"Unknown resource type: {resource_type}")

        model: type[Any] = cast("type[Any]", mapping["model"])
        id_field: str = cast("str", mapping["id_field"])

        with self.db_client.get_session() as session:
            # Check if already exists
            existing = session.execute(
                select(model).where(
                    model.tenant_id == tenant_id, model.user_id == user_id, getattr(model, id_field) == resource_id
                )
            ).scalar_one_or_none()

            if existing:
                # Return existing favorite
                return UserFavoriteResponse(
                    tenant_id=existing.tenant_id,
                    user_id=existing.user_id,
                    resource_id=getattr(existing, id_field),
                    resource_type=resource_type,
                    created_at=existing.created_at,
                    updated_at=existing.updated_at,
                    created_by=existing.created_by,
                    updated_by=existing.updated_by,
                )

            # Create new favorite
            favorite = model(
                tenant_id=tenant_id, user_id=user_id, created_by=user_id, updated_by=user_id, **{id_field: resource_id}
            )
            session.add(favorite)
            session.flush()

            logger.info("User favorite added", extra={"resource_id": resource_id})

            result = UserFavoriteResponse(
                tenant_id=favorite.tenant_id,
                user_id=favorite.user_id,
                resource_id=getattr(favorite, id_field),
                resource_type=resource_type,
                created_at=favorite.created_at,
                updated_at=favorite.updated_at,
                created_by=favorite.created_by,
                updated_by=favorite.updated_by,
            )

            # Invalidate cache
            self._invalidate_cache(tenant_id, user_id, resource_type)

            return result

    def remove_user_favorite(self, tenant_id: str, user_id: str, resource_type: str, resource_id: str) -> None:
        """
        Remove a resource from user favorites.

        Args:
            tenant_id: The ID of the tenant
            user_id: The ID of the user
            resource_type: Type of resource (chat-agents, autonomous-agents, etc.)
            resource_id: The ID of the resource to unfavorite
        """
        logger.info(
            "Removing user favorite",
            extra={
                "tenant_id": tenant_id,
                "user_id": user_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
            },
        )

        mapping = RESOURCE_FAVORITE_MAPPING.get(resource_type)
        if not mapping:
            raise ValueError(f"Unknown resource type: {resource_type}")

        model: type[Any] = cast("type[Any]", mapping["model"])
        id_field: str = cast("str", mapping["id_field"])

        with self.db_client.get_session() as session:
            session.execute(
                delete(model).where(
                    model.tenant_id == tenant_id, model.user_id == user_id, getattr(model, id_field) == resource_id
                )
            )

            logger.info("User favorite removed", extra={"resource_id": resource_id})

            # Invalidate cache
            self._invalidate_cache(tenant_id, user_id, resource_type)

    def _invalidate_cache(self, tenant_id: str, user_id: str, resource_type: str) -> None:
        """Invalidate the user favorites cache for both specific and unified views."""
        if self.cache_client:
            cache_key = f"user_favorites:{resource_type}:tenant:{tenant_id}:user:{user_id}"
            unified_cache_key = f"user_favorites:all:tenant:{tenant_id}:user:{user_id}"
            try:
                self.cache_client.client.delete(cache_key)
                self.cache_client.client.delete(unified_cache_key)
                logger.debug("Invalidated user favorites cache")
            except Exception as e:
                logger.warning("Failed to invalidate user favorites cache: %s", e)
