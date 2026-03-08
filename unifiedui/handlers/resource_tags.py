"""Central handler for resource tag operations.

This handler provides a unified interface for managing tags on all
resource types that support tagging.

Supported resource types:
- chat_agent
- autonomous_agent
- chat_widget
- credential

This handler consolidates tag-related logic that was previously
duplicated across individual resource handlers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, select

from unifiedui.core.database.models import (
    AutonomousAgent,
    AutonomousAgentTag,
    ChatAgent,
    ChatAgentTag,
    ChatWidget,
    ChatWidgetTag,
    Credential,
    CredentialTag,
    Tag,
)
from unifiedui.logger import get_logger

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from unifiedui.caching.client import CacheClient
    from unifiedui.core.database.client import SQLAlchemyClient
    from unifiedui.core.identity.users import ContextIdentityUser

logger = get_logger(__name__)


# Configuration mapping for each resource type
RESOURCE_TAG_CONFIG: dict[str, dict[str, Any]] = {
    "chat_agent": {
        "resource_model": ChatAgent,
        "tag_model": ChatAgentTag,
        "id_field": "chat_agent_id",
        "cache_prefix": "chat_agents",
    },
    "autonomous_agent": {
        "resource_model": AutonomousAgent,
        "tag_model": AutonomousAgentTag,
        "id_field": "autonomous_agent_id",
        "cache_prefix": "autonomous_agents",
    },
    "chat_widget": {
        "resource_model": ChatWidget,
        "tag_model": ChatWidgetTag,
        "id_field": "chat_widget_id",
        "cache_prefix": "chat_widgets",
    },
    "credential": {
        "resource_model": Credential,
        "tag_model": CredentialTag,
        "id_field": "credential_id",
        "cache_prefix": "credentials",
    },
}


class ResourceTagsHandler:
    """
    Central handler for resource tag operations.

    This handler provides a unified interface for managing tags across
    all resource types that support tagging (chat_agent, credential, etc.).

    Usage:
        handler = ResourceTagsHandler(db_client, cache_client)

        # Get tags for a resource
        tags = handler.get_resource_tags(
            resource_type="chat_agent",
            tenant_id="...",
            resource_id="..."
        )

        # Set tags for a resource (replaces existing tags)
        handler.set_resource_tags(
            resource_type="chat_agent",
            tenant_id="...",
            resource_id="...",
            tag_names=["tag1", "tag2"],
            user=user
        )
    """

    def __init__(self, db_client: SQLAlchemyClient, cache_client: CacheClient | None = None):
        """
        Initialize the resource tags handler.

        Args:
            db_client: SQLAlchemy database client instance
            cache_client: Optional cache client for Redis caching
        """
        self.db_client = db_client
        self.cache_client = cache_client

    def _get_config(self, resource_type: str) -> dict[str, Any]:
        """Get configuration for a resource type."""
        if resource_type not in RESOURCE_TAG_CONFIG:
            raise ValueError(
                f"Unknown resource type: {resource_type}. Supported types: {list(RESOURCE_TAG_CONFIG.keys())}"
            )
        return RESOURCE_TAG_CONFIG[resource_type]

    def _verify_resource_exists(self, session: Session, resource_type: str, tenant_id: str, resource_id: str) -> bool:
        """
        Verify that a resource exists.

        Args:
            session: SQLAlchemy session
            resource_type: Type of resource
            tenant_id: Tenant ID
            resource_id: Resource ID

        Returns:
            True if resource exists

        Raises:
            ValueError: If resource not found
        """
        config = self._get_config(resource_type)
        model = config["resource_model"]

        result = session.execute(
            select(model).where(model.id == resource_id, model.tenant_id == tenant_id)
        ).scalar_one_or_none()

        if not result:
            raise ValueError(f"{resource_type} with id {resource_id} not found")
        return True

    def get_resource_tags(
        self, resource_type: str, tenant_id: str, resource_id: str, use_cache: bool = True
    ) -> dict[str, Any]:
        """
        Get tags for a specific resource.

        Args:
            resource_type: Type of resource
            tenant_id: Tenant ID
            resource_id: Resource ID
            use_cache: Whether to use caching

        Returns:
            Dict with resource_id, resource_type, tenant_id, and tags list
        """
        logger.info(
            "Getting resource tags",
            extra={"resource_type": resource_type, "tenant_id": tenant_id, "resource_id": resource_id},
        )

        config = self._get_config(resource_type)
        tag_model = config["tag_model"]
        id_field = config["id_field"]
        config["cache_prefix"]

        cache_key = f"tags:{resource_type}:{resource_id}:tenant:{tenant_id}"

        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug("Returning cached tags for %s", resource_type)
                    return cached_data
            except Exception as e:
                logger.warning("Failed to get cached tags: %s", e)

        with self.db_client.get_session() as session:
            # Verify resource exists
            self._verify_resource_exists(session, resource_type, tenant_id, resource_id)

            # Get all tags for this resource
            query = (
                select(tag_model, Tag)
                .join(Tag, tag_model.tag_id == Tag.id)
                .where(getattr(tag_model, id_field) == resource_id, tag_model.tenant_id == tenant_id)
            )
            results = session.execute(query).all()

            tags = [{"id": tag.id, "name": tag.name} for _, tag in results]

            result = {"resource_id": resource_id, "resource_type": resource_type, "tenant_id": tenant_id, "tags": tags}

            # Cache the result
            if use_cache and self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, result, ttl=300)
                    logger.debug("Cached tags for %s", resource_type)
                except Exception as e:
                    logger.warning("Failed to cache tags: %s", e)

            return result

    def set_resource_tags(
        self, resource_type: str, tenant_id: str, resource_id: str, tag_names: list[str], user: ContextIdentityUser
    ) -> dict[str, Any]:
        """
        Set tags for a resource (replaces existing tags).

        This method will:
        1. Create any tags that don't exist
        2. Remove all existing tag associations for the resource
        3. Add the new tag associations

        Args:
            resource_type: Type of resource
            tenant_id: Tenant ID
            resource_id: Resource ID
            tag_names: List of tag names to set
            user: User context for audit fields

        Returns:
            Dict with resource_id, resource_type, tenant_id, and updated tags list
        """
        logger.info(
            "Setting resource tags",
            extra={
                "resource_type": resource_type,
                "tenant_id": tenant_id,
                "resource_id": resource_id,
                "tag_count": len(tag_names),
            },
        )

        config = self._get_config(resource_type)
        tag_model = config["tag_model"]
        id_field = config["id_field"]

        user_id = user.identity.get_id()

        with self.db_client.get_session() as session:
            # Verify resource exists
            self._verify_resource_exists(session, resource_type, tenant_id, resource_id)

            # Delete existing tag associations
            delete_stmt = delete(tag_model).where(
                getattr(tag_model, id_field) == resource_id, tag_model.tenant_id == tenant_id
            )
            session.execute(delete_stmt)

            # Get or create tags and add associations
            tags = []
            for tag_name in tag_names:
                tag = self._get_or_create_tag(session, tenant_id, tag_name, user_id)
                tags.append({"id": tag.id, "name": tag.name})

                # Create tag association
                tag_assoc_kwargs = {
                    "tenant_id": tenant_id,
                    "tag_id": tag.id,
                    id_field: resource_id,
                    "created_by": user_id,
                    "updated_by": user_id,
                }
                tag_assoc = tag_model(**tag_assoc_kwargs)
                session.add(tag_assoc)

            session.commit()
            logger.info("Set %s tags for %s", len(tags), resource_type)

            # Invalidate caches
            self._invalidate_resource_caches(resource_type, tenant_id, resource_id)

            return {"resource_id": resource_id, "resource_type": resource_type, "tenant_id": tenant_id, "tags": tags}

    def add_resource_tag(
        self, resource_type: str, tenant_id: str, resource_id: str, tag_name: str, user: ContextIdentityUser
    ) -> dict[str, Any]:
        """
        Add a single tag to a resource.

        Args:
            resource_type: Type of resource
            tenant_id: Tenant ID
            resource_id: Resource ID
            tag_name: Tag name to add
            user: User context for audit fields

        Returns:
            Dict with tag info
        """
        logger.info(
            "Adding resource tag",
            extra={
                "resource_type": resource_type,
                "tenant_id": tenant_id,
                "resource_id": resource_id,
                "tag_name": tag_name,
            },
        )

        config = self._get_config(resource_type)
        tag_model = config["tag_model"]
        id_field = config["id_field"]

        user_id = user.identity.get_id()

        with self.db_client.get_session() as session:
            # Verify resource exists
            self._verify_resource_exists(session, resource_type, tenant_id, resource_id)

            # Get or create tag
            tag = self._get_or_create_tag(session, tenant_id, tag_name, user_id)

            # Check if association already exists
            existing = session.execute(
                select(tag_model).where(
                    getattr(tag_model, id_field) == resource_id,
                    tag_model.tag_id == tag.id,
                    tag_model.tenant_id == tenant_id,
                )
            ).scalar_one_or_none()

            if not existing:
                # Create tag association
                tag_assoc_kwargs = {
                    "tenant_id": tenant_id,
                    "tag_id": tag.id,
                    id_field: resource_id,
                    "created_by": user_id,
                    "updated_by": user_id,
                }
                tag_assoc = tag_model(**tag_assoc_kwargs)
                session.add(tag_assoc)
                session.commit()
                logger.info("Added tag to %s", resource_type)
            else:
                logger.info("Tag already exists on %s", resource_type)

            # Invalidate caches
            self._invalidate_resource_caches(resource_type, tenant_id, resource_id)

            return {"id": tag.id, "name": tag.name}

    def remove_resource_tag(self, resource_type: str, tenant_id: str, resource_id: str, tag_id: int) -> None:
        """
        Remove a tag from a resource.

        Args:
            resource_type: Type of resource
            tenant_id: Tenant ID
            resource_id: Resource ID
            tag_id: Tag ID to remove
        """
        logger.info(
            "Removing resource tag",
            extra={
                "resource_type": resource_type,
                "tenant_id": tenant_id,
                "resource_id": resource_id,
                "tag_id": tag_id,
            },
        )

        config = self._get_config(resource_type)
        tag_model = config["tag_model"]
        id_field = config["id_field"]

        with self.db_client.get_session() as session:
            # Verify resource exists
            self._verify_resource_exists(session, resource_type, tenant_id, resource_id)

            # Delete tag association
            delete_stmt = delete(tag_model).where(
                getattr(tag_model, id_field) == resource_id,
                tag_model.tag_id == tag_id,
                tag_model.tenant_id == tenant_id,
            )
            result = session.execute(delete_stmt)
            session.commit()

            if result.rowcount == 0:  # type: ignore[attr-defined]
                logger.warning("Tag association not found for %s", resource_type)
            else:
                logger.info("Removed tag from %s", resource_type)

            # Invalidate caches
            self._invalidate_resource_caches(resource_type, tenant_id, resource_id)

    def _get_or_create_tag(self, session: Session, tenant_id: str, name: str, user_id: str) -> Tag:
        """
        Get an existing tag or create a new one.

        Args:
            session: SQLAlchemy session
            tenant_id: Tenant ID
            name: Tag name
            user_id: User ID for audit fields

        Returns:
            Tag model instance
        """
        # Query with uppercase name since @validates converts to uppercase
        tag = session.execute(
            select(Tag).where(Tag.tenant_id == tenant_id, Tag.name == name.upper())
        ).scalar_one_or_none()

        if tag:
            return tag

        # Create new tag (name will be uppercased by @validates decorator)
        tag = Tag(tenant_id=tenant_id, name=name, created_by=user_id, updated_by=user_id)
        session.add(tag)
        try:
            session.flush()
        except Exception:
            # If flush fails due to unique constraint (race condition),
            # re-query for the tag (another request might have created it)
            session.rollback()
            tag = session.execute(
                select(Tag).where(
                    Tag.tenant_id == tenant_id,
                    Tag.name == name.upper(),  # Query with uppercase
                )
            ).scalar_one_or_none()
            if not tag:
                raise

        logger.info("Created new tag", extra={"tag_id": tag.id, "tag_name": name})

        # Invalidate tag list cache
        self._invalidate_tag_list_cache(tenant_id)

        return tag

    def _invalidate_resource_caches(self, resource_type: str, tenant_id: str, resource_id: str) -> None:
        """Invalidate caches related to a resource's tags."""
        if self.cache_client:
            config = self._get_config(resource_type)
            cache_prefix = config["cache_prefix"]

            # Invalidate resource tags cache
            cache_key = f"tags:{resource_type}:{resource_id}:tenant:{tenant_id}"
            self.cache_client.client.delete(cache_key)

            # Invalidate resource detail cache
            detail_pattern = f"{cache_prefix}:detail:tenant:{tenant_id}:*{resource_id}*"
            self.cache_client.client.delete_pattern(detail_pattern)

            # Invalidate list caches (since tags are included in list responses)
            list_pattern = f"{cache_prefix}:list:tenant:{tenant_id}:*"
            self.cache_client.client.delete_pattern(list_pattern)

    def _invalidate_tag_list_cache(self, tenant_id: str) -> None:
        """Invalidate tag list cache for a tenant."""
        if self.cache_client:
            cache_key = f"tags:list:tenant:{tenant_id}"
            self.cache_client.client.delete(cache_key)

    @staticmethod
    def get_supported_resource_types() -> list[str]:
        """Get list of supported resource types for tagging."""
        return list(RESOURCE_TAG_CONFIG.keys())
