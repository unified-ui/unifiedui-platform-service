"""Handler for tag operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

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
    ExternalApp,
    ExternalAppTag,
    Tag,
    TenantAIModel,
    TenantAIModelTag,
    Tool,
    ToolTag,
)
from unifiedui.exc.tags import TagNotFoundError
from unifiedui.logger import get_logger
from unifiedui.schema.responses.tags import TagResponse, TagSummary

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from unifiedui.caching.client import CacheClient
    from unifiedui.core.database.client import SQLAlchemyClient
    from unifiedui.core.identity.users import ContextIdentityUser

logger = get_logger(__name__)


# Mapping of resource types to their models and tag junction tables
RESOURCE_TAG_MAPPING = {
    "chat_agent": {
        "model": ChatAgent,
        "tag_model": ChatAgentTag,
        "id_field": "chat_agent_id",
        "cache_key_pattern": "chat_agents:detail:tenant:{tenant_id}:chat_agent:{resource_id}",
    },
    "autonomous_agent": {
        "model": AutonomousAgent,
        "tag_model": AutonomousAgentTag,
        "id_field": "autonomous_agent_id",
        "cache_key_pattern": "autonomous_agents:detail:tenant:{tenant_id}:agent:{resource_id}",
    },
    "chat_widget": {
        "model": ChatWidget,
        "tag_model": ChatWidgetTag,
        "id_field": "chat_widget_id",
        "cache_key_pattern": "chat_widgets:detail:tenant:{tenant_id}:cw:{resource_id}",
    },
    "credential": {
        "model": Credential,
        "tag_model": CredentialTag,
        "id_field": "credential_id",
        "cache_key_pattern": "credentials:detail:tenant:{tenant_id}:cred:{resource_id}",
    },
    "tool": {
        "model": Tool,
        "tag_model": ToolTag,
        "id_field": "tool_id",
        "cache_key_pattern": "tools:detail:tenant:{tenant_id}:tool:{resource_id}",
    },
    "external_app": {
        "model": ExternalApp,
        "tag_model": ExternalAppTag,
        "id_field": "external_app_id",
        "cache_key_pattern": "external_apps:detail:tenant:{tenant_id}:ea:{resource_id}",
    },
    "tenant_ai_model": {
        "model": TenantAIModel,
        "tag_model": TenantAIModelTag,
        "id_field": "tenant_ai_model_id",
        "cache_key_pattern": "tenant_ai_models:detail:tenant:{tenant_id}:aim:{resource_id}",
    },
}


class TagHandler:
    """Handler for tag operations."""

    def __init__(self, db_client: SQLAlchemyClient, cache_client: CacheClient | None = None):
        """
        Initialize the tag handler.

        Args:
            db_client: SQLAlchemy database client instance
            cache_client: Optional cache client for Redis caching
        """
        self.db_client = db_client
        self.cache_client = cache_client

    def list_tags(
        self, tenant_id: str, name_filter: str | None = None, skip: int = 0, limit: int = 100, use_cache: bool = True
    ) -> list[TagSummary]:
        """
        Get a list of tags for a tenant.

        Args:
            tenant_id: The ID of the tenant
            name_filter: Optional filter by tag name (disables caching)
            skip: Number of tags to skip (pagination)
            limit: Maximum number of tags to return
            use_cache: Whether to use caching (ignored if name_filter, skip, or limit are set)

        Returns:
            List of TagSummary (id and name only)
        """
        logger.info(
            "Listing tags", extra={"tenant_id": tenant_id, "name_filter": name_filter, "skip": skip, "limit": limit}
        )

        # Disable cache when filtering by name or using pagination
        should_cache = use_cache and name_filter is None and skip == 0 and limit == 100

        cache_key = f"tags:list:tenant:{tenant_id}"

        # Check cache
        if should_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug("Returning cached tag list")
                    return [TagSummary(**item) for item in cached_data]
            except Exception as e:
                logger.warning("Failed to get cached tag list: %s", e)

        with self.db_client.get_session() as session:
            # Data query with pagination (no total count needed)
            query = select(Tag).where(Tag.tenant_id == tenant_id)

            if name_filter:
                query = query.where(Tag.name.ilike(f"%{name_filter}%"))

            query = query.order_by(Tag.name).offset(skip).limit(limit)
            tags = session.execute(query).scalars().all()

            logger.info("Retrieved tags", extra={"count": len(tags)})
            tag_summaries = [TagSummary(id=tag.id, name=tag.name) for tag in tags]

            # Cache the result (only if default pagination and not filtering)
            if should_cache and self.cache_client:
                try:
                    data = [t.model_dump() for t in tag_summaries]
                    self.cache_client.client.set(cache_key, data, ttl=300)
                    logger.debug("Cached tag list")
                except Exception as e:
                    logger.warning("Failed to cache tag list: %s", e)

            return tag_summaries

    def list_tags_for_resource(
        self,
        tenant_id: str,
        resource_type: str,
        name_filter: str | None = None,
        skip: int = 0,
        limit: int = 100,
        use_cache: bool = True,
    ) -> list[TagSummary]:
        """
        Get a list of tags that are applied to a specific resource type.

        Args:
            tenant_id: The ID of the tenant
            resource_type: Type of resource (chat_agent, autonomous_agent, etc.)
            name_filter: Optional filter by tag name
            skip: Number of tags to skip (pagination)
            limit: Maximum number of tags to return
            use_cache: Whether to use caching

        Returns:
            List of TagSummary (id and name only)

        Raises:
            ValueError: If resource_type is not supported
        """
        if resource_type not in RESOURCE_TAG_MAPPING:
            raise ValueError(f"Unsupported resource type: {resource_type}")

        logger.info(
            "Listing tags for resource type",
            extra={
                "tenant_id": tenant_id,
                "resource_type": resource_type,
                "name_filter": name_filter,
                "skip": skip,
                "limit": limit,
            },
        )

        # Disable cache when filtering or paginating
        should_cache = use_cache and name_filter is None and skip == 0 and limit == 100

        cache_key = f"tags:list:tenant:{tenant_id}:resource:{resource_type}"

        # Check cache
        if should_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug("Returning cached resource tag list")
                    return [TagSummary(**item) for item in cached_data]
            except Exception as e:
                logger.warning("Failed to get cached resource tag list: %s", e)

        config = RESOURCE_TAG_MAPPING[resource_type]
        tag_model: type[Any] = cast("type[Any]", config["tag_model"])

        with self.db_client.get_session() as session:
            # Data query (no total count needed)
            query = select(Tag).join(tag_model, Tag.id == tag_model.tag_id).where(Tag.tenant_id == tenant_id)

            if name_filter:
                query = query.where(Tag.name.ilike(f"%{name_filter}%"))

            query = query.order_by(Tag.name).distinct().offset(skip).limit(limit)
            tags = session.execute(query).scalars().all()

            logger.info("Retrieved tags for resource type", extra={"count": len(tags), "resource_type": resource_type})
            tag_summaries = [TagSummary(id=tag.id, name=tag.name) for tag in tags]

            # Cache the result (only if default pagination and not filtering)
            if should_cache and self.cache_client:
                try:
                    data = [t.model_dump() for t in tag_summaries]
                    self.cache_client.client.set(cache_key, data, ttl=300)
                    logger.debug("Cached resource tag list")
                except Exception as e:
                    logger.warning("Failed to cache resource tag list: %s", e)

            return tag_summaries

    def get_tag(self, tenant_id: str, tag_id: int, use_cache: bool = True) -> TagResponse:
        """
        Get a specific tag by ID.

        Args:
            tenant_id: The ID of the tenant
            tag_id: The ID of the tag
            use_cache: Whether to use caching

        Returns:
            TagResponse

        Raises:
            TagNotFoundError: If tag not found
        """
        logger.info("Getting tag", extra={"tenant_id": tenant_id, "tag_id": tag_id})

        cache_key = f"tags:detail:tenant:{tenant_id}:tag:{tag_id}"

        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug("Returning cached tag")
                    return TagResponse(**cached_data)
            except Exception as e:
                logger.warning("Failed to get cached tag: %s", e)

        with self.db_client.get_session() as session:
            tag = session.execute(select(Tag).where(Tag.id == tag_id, Tag.tenant_id == tenant_id)).scalar_one_or_none()

            if not tag:
                raise TagNotFoundError(tag_id)

            result = self._model_to_response(tag)

            # Cache the result
            if use_cache and self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, result.model_dump(), ttl=300)
                    logger.debug("Cached tag detail")
                except Exception as e:
                    logger.warning("Failed to cache tag: %s", e)

            return result

    def create_tag(self, tenant_id: str, name: str, user: ContextIdentityUser) -> TagResponse:
        """
        Create a new tag.

        Args:
            tenant_id: The ID of the tenant
            name: Tag name
            user: ContextIdentityUser object

        Returns:
            Created TagResponse
        """
        logger.info("Creating tag", extra={"tenant_id": tenant_id, "tag_name": name})

        user_id = user.identity.get_id()

        with self.db_client.get_session() as session:
            tag = Tag(tenant_id=tenant_id, name=name, created_by=user_id, updated_by=user_id)
            session.add(tag)
            session.flush()

            logger.info("Tag created", extra={"tag_id": tag.id})
            result = self._model_to_response(tag)

            # Invalidate list cache
            self._invalidate_tag_list_cache(tenant_id)

            return result

    def get_or_create_tag(self, session: Session, tenant_id: str, name: str, user_id: str) -> Tag:
        """
        Get an existing tag or create a new one within an existing session.

        Args:
            session: SQLAlchemy session
            tenant_id: The ID of the tenant
            name: Tag name
            user_id: User ID for audit fields

        Returns:
            Tag model instance
        """
        # Try to find existing tag
        tag = session.execute(select(Tag).where(Tag.tenant_id == tenant_id, Tag.name == name)).scalar_one_or_none()

        if tag:
            return tag

        # Create new tag
        tag = Tag(tenant_id=tenant_id, name=name, created_by=user_id, updated_by=user_id)
        session.add(tag)
        session.flush()

        logger.info("Created new tag during resource tagging", extra={"tag_id": tag.id, "tag_name": name})
        return tag

    def delete_tag(self, tenant_id: str, tag_id: int) -> None:
        """
        Delete a tag.

        Permission check (TENANT_GLOBAL_ADMIN or creator) is handled by @check_permissions decorator.

        Args:
            tenant_id: The ID of the tenant
            tag_id: The ID of the tag

        Raises:
            TagNotFoundError: If tag not found
        """
        logger.info("Deleting tag", extra={"tenant_id": tenant_id, "tag_id": tag_id})

        with self.db_client.get_session() as session:
            tag = session.execute(select(Tag).where(Tag.id == tag_id, Tag.tenant_id == tenant_id)).scalar_one_or_none()

            if not tag:
                raise TagNotFoundError(tag_id)

            # Before deleting, find all resources using this tag for cache invalidation
            affected_resources = self._find_resources_using_tag(session, tenant_id, tag_id)

            session.delete(tag)
            logger.info("Tag deleted", extra={"tag_id": tag_id})

            # Invalidate caches
            self._invalidate_tag_list_cache(tenant_id)
            self._invalidate_tag_detail_cache(tenant_id, tag_id)

            # Invalidate caches for all affected resources
            for resource_type, resource_id in affected_resources:
                self._invalidate_resource_detail_cache(tenant_id, resource_type, resource_id)

    def _find_resources_using_tag(self, session: Session, tenant_id: str, tag_id: int) -> list[tuple]:
        """
        Find all resources that use a specific tag.

        Args:
            session: SQLAlchemy session
            tenant_id: The tenant ID
            tag_id: The tag ID

        Returns:
            List of (resource_type, resource_id) tuples
        """
        affected = []

        for resource_type, mapping in RESOURCE_TAG_MAPPING.items():
            tag_model: type[Any] = cast("type[Any]", mapping["tag_model"])
            id_field: str = cast("str", mapping["id_field"])

            results = (
                session.execute(
                    select(getattr(tag_model, id_field)).where(
                        tag_model.tag_id == tag_id, tag_model.tenant_id == tenant_id
                    )
                )
                .scalars()
                .all()
            )

            for resource_id in results:
                affected.append((resource_type, resource_id))

        return affected

    def get_resource_tags(
        self, tenant_id: str, resource_type: str, resource_id: str, use_cache: bool = True
    ) -> list[TagResponse]:
        """
        Get tags for a specific resource.

        Args:
            tenant_id: The ID of the tenant
            resource_type: Type of resource (chat_agent, autonomous_agent, etc.)
            resource_id: The ID of the resource
            use_cache: Whether to use caching

        Returns:
            List of TagResponse objects
        """
        logger.info(
            "Getting resource tags",
            extra={"tenant_id": tenant_id, "resource_type": resource_type, "resource_id": resource_id},
        )

        mapping = RESOURCE_TAG_MAPPING.get(resource_type)
        if not mapping:
            raise ValueError(f"Unknown resource type: {resource_type}")

        cache_key = f"tags:{resource_type}:{resource_id}:tenant:{tenant_id}"

        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug("Returning cached resource tags")
                    return [TagResponse(**item) for item in cached_data]
            except Exception as e:
                logger.warning("Failed to get cached resource tags: %s", e)

        tag_model: type[Any] = cast("type[Any]", mapping["tag_model"])
        id_field: str = cast("str", mapping["id_field"])

        with self.db_client.get_session() as session:
            # Join tag table with junction table
            query = (
                select(Tag)
                .join(tag_model, Tag.id == tag_model.tag_id)
                .where(getattr(tag_model, id_field) == resource_id, tag_model.tenant_id == tenant_id)
                .order_by(Tag.name)
            )

            tags = session.execute(query).scalars().all()
            tag_responses = [self._model_to_response(tag) for tag in tags]

            # Cache the result
            if use_cache and self.cache_client:
                try:
                    data = [t.model_dump() for t in tag_responses]
                    self.cache_client.client.set(cache_key, data, ttl=300)
                    logger.debug("Cached resource tags")
                except Exception as e:
                    logger.warning("Failed to cache resource tags: %s", e)

            return tag_responses

    def set_resource_tags(
        self, tenant_id: str, resource_type: str, resource_id: str, tag_names: list[str], user: ContextIdentityUser
    ) -> list[TagResponse]:
        """
        Set tags for a resource. Creates missing tags and replaces existing associations.

        Args:
            tenant_id: The ID of the tenant
            resource_type: Type of resource (chat_agent, autonomous_agent, etc.)
            resource_id: The ID of the resource
            tag_names: List of tag names to set
            user: ContextIdentityUser object

        Returns:
            List of TagResponse objects with the updated tags
        """
        logger.info(
            "Setting resource tags",
            extra={
                "tenant_id": tenant_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "tag_count": len(tag_names),
            },
        )

        mapping = RESOURCE_TAG_MAPPING.get(resource_type)
        if not mapping:
            raise ValueError(f"Unknown resource type: {resource_type}")

        tag_model: type[Any] = cast("type[Any]", mapping["tag_model"])
        id_field: str = cast("str", mapping["id_field"])
        user_id = user.identity.get_id()

        with self.db_client.get_session() as session:
            # Remove existing tag associations for this resource
            session.execute(
                delete(tag_model).where(getattr(tag_model, id_field) == resource_id, tag_model.tenant_id == tenant_id)
            )

            # Get or create tags and create new associations
            tags = []
            for name in tag_names:
                if not name.strip():
                    continue

                tag = self.get_or_create_tag(session, tenant_id, name.strip(), user_id)
                tags.append(tag)

                # Create association with audit fields
                association = tag_model(
                    tenant_id=tenant_id,
                    tag_id=tag.id,
                    created_by=user_id,
                    updated_by=user_id,
                    **{id_field: resource_id},
                )
                session.add(association)

            session.flush()

            logger.info("Resource tags set", extra={"tag_count": len(tags)})
            tag_responses = [self._model_to_response(tag) for tag in tags]

            # Invalidate caches
            self._invalidate_resource_tags_cache(tenant_id, resource_type, resource_id)
            self._invalidate_resource_detail_cache(tenant_id, resource_type, resource_id)
            self._invalidate_tag_list_cache(tenant_id)

            return tag_responses

    def delete_resource_tags(self, tenant_id: str, resource_type: str, resource_id: str) -> None:
        """
        Remove all tags from a resource.

        Args:
            tenant_id: The ID of the tenant
            resource_type: Type of resource (chat_agent, autonomous_agent, etc.)
            resource_id: The ID of the resource
        """
        logger.info(
            "Deleting resource tags",
            extra={"tenant_id": tenant_id, "resource_type": resource_type, "resource_id": resource_id},
        )

        mapping = RESOURCE_TAG_MAPPING.get(resource_type)
        if not mapping:
            raise ValueError(f"Unknown resource type: {resource_type}")

        tag_model: type[Any] = cast("type[Any]", mapping["tag_model"])
        id_field: str = cast("str", mapping["id_field"])

        with self.db_client.get_session() as session:
            session.execute(
                delete(tag_model).where(getattr(tag_model, id_field) == resource_id, tag_model.tenant_id == tenant_id)
            )

            logger.info("Resource tags deleted")

            # Invalidate caches
            self._invalidate_resource_tags_cache(tenant_id, resource_type, resource_id)
            self._invalidate_resource_detail_cache(tenant_id, resource_type, resource_id)

    def get_tags_for_resource_list(
        self, session: Session, tenant_id: str, resource_type: str, resource_ids: list[str]
    ) -> dict:
        """
        Get tags for multiple resources efficiently (for list endpoints).

        Args:
            session: SQLAlchemy session
            tenant_id: The ID of the tenant
            resource_type: Type of resource
            resource_ids: List of resource IDs

        Returns:
            Dict mapping resource_id to list of TagSummary
        """
        if not resource_ids:
            return {}

        mapping = RESOURCE_TAG_MAPPING.get(resource_type)
        if not mapping:
            return {}

        tag_model: type[Any] = cast("type[Any]", mapping["tag_model"])
        id_field: str = cast("str", mapping["id_field"])

        # Query all tags for all resources in one query
        query = (
            select(Tag, getattr(tag_model, id_field))
            .join(tag_model, Tag.id == tag_model.tag_id)
            .where(getattr(tag_model, id_field).in_(resource_ids), tag_model.tenant_id == tenant_id)
            .order_by(Tag.name)
        )

        results = session.execute(query).all()

        # Group by resource ID
        tags_by_resource: dict[str, list[TagSummary]] = {}
        for tag, res_id in results:
            if res_id not in tags_by_resource:
                tags_by_resource[res_id] = []
            tags_by_resource[res_id].append(TagSummary(id=tag.id, name=tag.name))

        return tags_by_resource

    def _invalidate_tag_list_cache(self, tenant_id: str) -> None:
        """Invalidate the tag list cache for a tenant."""
        if self.cache_client:
            try:
                cache_key = f"tags:list:tenant:{tenant_id}"
                self.cache_client.client.delete(cache_key)
                logger.debug("Invalidated tag list cache")
            except Exception as e:
                logger.warning("Failed to invalidate tag list cache: %s", e)

    def _invalidate_tag_detail_cache(self, tenant_id: str, tag_id: int) -> None:
        """Invalidate the tag detail cache."""
        if self.cache_client:
            try:
                cache_key = f"tags:detail:tenant:{tenant_id}:tag:{tag_id}"
                self.cache_client.client.delete(cache_key)
                logger.debug("Invalidated tag detail cache")
            except Exception as e:
                logger.warning("Failed to invalidate tag detail cache: %s", e)

    def _invalidate_resource_tags_cache(self, tenant_id: str, resource_type: str, resource_id: str) -> None:
        """Invalidate the resource tags cache."""
        if self.cache_client:
            try:
                cache_key = f"tags:{resource_type}:{resource_id}:tenant:{tenant_id}"
                self.cache_client.client.delete(cache_key)
                logger.debug("Invalidated resource tags cache")
            except Exception as e:
                logger.warning("Failed to invalidate resource tags cache: %s", e)

    def _invalidate_resource_detail_cache(self, tenant_id: str, resource_type: str, resource_id: str) -> None:
        """Invalidate the parent resource detail cache when tags change."""
        if self.cache_client:
            mapping = RESOURCE_TAG_MAPPING.get(resource_type)
            if not mapping or "cache_key_pattern" not in mapping:
                return

            try:
                cache_key_pattern: str = cast("str", mapping["cache_key_pattern"])
                cache_key = cache_key_pattern.format(tenant_id=tenant_id, resource_id=resource_id)
                self.cache_client.client.delete(cache_key)
                logger.debug("Invalidated %s detail cache", resource_type)
            except Exception as e:
                logger.warning("Failed to invalidate %s detail cache: %s", resource_type, e)

    @staticmethod
    def _model_to_response(tag: Tag) -> TagResponse:
        """Convert Tag model to TagResponse."""
        return TagResponse(
            id=tag.id,
            tenant_id=tag.tenant_id,
            name=tag.name,
            created_at=tag.created_at,
            updated_at=tag.updated_at,
            created_by=tag.created_by,
            updated_by=tag.updated_by,
        )
