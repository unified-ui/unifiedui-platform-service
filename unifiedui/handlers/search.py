"""Business logic handlers for global search operations."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import select, or_

from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.core.database.models import (
    Application,
    ApplicationMember,
    ApplicationTag,
    AutonomousAgent,
    AutonomousAgentMember,
    AutonomousAgentTag,
    Conversation,
    ConversationMember,
    ReActAgent,
    ReActAgentMember,
    ReActAgentTag,
    Tag,
)
from unifiedui.core.database.enums import TenantRolesEnum, PrincipalTypeEnum
from unifiedui.caching.client import CacheClient

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser

from unifiedui.schema.responses.search import SearchResponse, SearchResultItem
from unifiedui.logger import get_logger

logger = get_logger(__name__)

VALID_SEARCH_TYPES = {"application", "autonomous_agent", "conversation", "re_act_agent"}

SEARCH_TYPE_CONFIG = {
    "application": {
        "entity_model": Application,
        "member_model": ApplicationMember,
        "entity_id_field": "application_id",
        "tag_model": ApplicationTag,
        "tag_entity_id_field": "application_id",
        "admin_roles": [
            TenantRolesEnum.GLOBAL_ADMIN,
            TenantRolesEnum.APPLICATIONS_ADMIN,
        ],
    },
    "autonomous_agent": {
        "entity_model": AutonomousAgent,
        "member_model": AutonomousAgentMember,
        "entity_id_field": "autonomous_agent_id",
        "tag_model": AutonomousAgentTag,
        "tag_entity_id_field": "autonomous_agent_id",
        "admin_roles": [
            TenantRolesEnum.GLOBAL_ADMIN,
            TenantRolesEnum.AUTONOMOUS_AGENTS_ADMIN,
        ],
    },
    "conversation": {
        "entity_model": Conversation,
        "member_model": ConversationMember,
        "entity_id_field": "conversation_id",
        "tag_model": None,
        "tag_entity_id_field": None,
        "admin_roles": [
            TenantRolesEnum.GLOBAL_ADMIN,
            TenantRolesEnum.CONVERSATIONS_ADMIN,
        ],
    },
    "re_act_agent": {
        "entity_model": ReActAgent,
        "member_model": ReActAgentMember,
        "entity_id_field": "re_act_agent_id",
        "tag_model": ReActAgentTag,
        "tag_entity_id_field": "re_act_agent_id",
        "admin_roles": [
            TenantRolesEnum.GLOBAL_ADMIN,
            TenantRolesEnum.REACT_AGENT_ADMIN,
        ],
    },
}


class SearchHandler:
    """Handler class for global search business logic."""

    def __init__(
        self,
        db_client: SQLAlchemyClient,
        cache_client: Optional[CacheClient] = None,
    ):
        """Initialize the search handler.

        Args:
            db_client: Database client for queries.
            cache_client: Optional cache client.
        """
        self.db_client = db_client
        self.cache_client = cache_client

    def _get_principal_ids(self, user: ContextIdentityUser) -> list[str]:
        """Get all principal IDs for a user including groups.

        Args:
            user: Authenticated user context.

        Returns:
            List of principal IDs (user + groups).
        """
        user_id = user.identity.get_id()
        identity_group_ids = [
            g.id for g in user.groups
            if g.principal_type == PrincipalTypeEnum.IDENTITY_GROUP.value
        ]
        custom_group_ids = [
            g.id for g in user.groups
            if g.principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value
        ]
        return [user_id] + identity_group_ids + custom_group_ids

    def _check_admin_for_type(
        self,
        user: ContextIdentityUser,
        tenant_id: str,
        admin_roles: list[TenantRolesEnum],
    ) -> bool:
        """Check if user has admin roles for a resource type.

        Args:
            user: Authenticated user context.
            tenant_id: Tenant ID to check.
            admin_roles: List of admin roles that grant full access.

        Returns:
            True if user has any of the admin roles.
        """
        matching_tenant = next(
            (t for t in user.tenants if t["tenant"]["id"] == tenant_id),
            None,
        )
        if not matching_tenant:
            return False
        user_roles = set(matching_tenant["roles"])
        return bool(user_roles & {r.value for r in admin_roles})

    def _load_tags_for_entities(
        self,
        session,
        tenant_id: str,
        tag_model,
        tag_entity_id_field: str,
        entity_ids: list[str],
    ) -> dict[str, list[str]]:
        """Load tags for a set of entities.

        Args:
            session: Database session.
            tenant_id: Tenant scope.
            tag_model: SQLAlchemy tag junction model.
            tag_entity_id_field: Field name of entity FK on tag model.
            entity_ids: List of entity IDs to load tags for.

        Returns:
            Dict mapping entity_id to list of tag names.
        """
        if not entity_ids or tag_model is None:
            return {}

        tag_query = (
            select(
                getattr(tag_model, tag_entity_id_field),
                Tag.name,
            )
            .join(Tag, tag_model.tag_id == Tag.id)
            .where(
                tag_model.tenant_id == tenant_id,
                getattr(tag_model, tag_entity_id_field).in_(entity_ids),
            )
        )
        tag_rows = session.execute(tag_query).all()

        tags_map: dict[str, list[str]] = {}
        for entity_id, tag_name in tag_rows:
            tags_map.setdefault(entity_id, []).append(tag_name)
        return tags_map

    def _search_entity_type(
        self,
        session,
        tenant_id: str,
        query: str,
        config: dict,
        principal_ids: list[str],
        is_admin: bool,
        limit: int,
    ) -> list[SearchResultItem]:
        """Search a single entity type with RBAC filtering.

        Args:
            session: Database session.
            tenant_id: Tenant scope.
            query: Search query string.
            config: Search type configuration dict.
            principal_ids: User principal IDs for filtering.
            is_admin: Whether user is admin for this type.
            limit: Maximum results.

        Returns:
            List of search result items.
        """
        entity_model = config["entity_model"]
        member_model = config["member_model"]
        entity_id_field = config["entity_id_field"]

        like_pattern = f"%{query}%"

        name_match = entity_model.name.ilike(like_pattern)
        desc_match = entity_model.description.ilike(like_pattern)

        base_filters = [entity_model.tenant_id == tenant_id]

        if not is_admin:
            member_subquery = (
                select(getattr(member_model, entity_id_field))
                .where(
                    member_model.tenant_id == tenant_id,
                    member_model.principal_id.in_(principal_ids),
                )
                .distinct()
            )
            base_filters.append(entity_model.id.in_(member_subquery))

        base_filters.append(or_(name_match, desc_match))

        search_query = (
            select(entity_model.id, entity_model.name, entity_model.description)
            .where(*base_filters)
            .limit(limit)
        )

        rows = session.execute(search_query).all()

        entity_ids = [r[0] for r in rows]
        tags_map = self._load_tags_for_entities(
            session,
            tenant_id,
            config["tag_model"],
            config["tag_entity_id_field"],
            entity_ids,
        )

        entity_type = [k for k, v in SEARCH_TYPE_CONFIG.items() if v is config][0]
        results: list[SearchResultItem] = []
        for entity_id, name, description in rows:
            match_field = "name" if query.lower() in (name or "").lower() else "description"
            results.append(SearchResultItem(
                type=entity_type,
                id=entity_id,
                name=name,
                description=description,
                match_field=match_field,
                is_active=None,
                tags=tags_map.get(entity_id, []),
            ))

        return results

    def search(
        self,
        tenant_id: str,
        user: ContextIdentityUser,
        query: str,
        types: Optional[list[str]] = None,
        limit: int = 10,
    ) -> SearchResponse:
        """Execute global search across entity types.

        Args:
            tenant_id: Tenant ID for scoping.
            user: Authenticated user context.
            query: Search query string.
            types: Entity types to search (None = all).
            limit: Maximum results per type.

        Returns:
            Search response with results.
        """
        if not query or not query.strip():
            return SearchResponse(results=[], total=0, query=query or "")

        query = query.strip()

        search_types = VALID_SEARCH_TYPES
        if types:
            search_types = VALID_SEARCH_TYPES & set(types)

        if not search_types:
            return SearchResponse(results=[], total=0, query=query)

        principal_ids = self._get_principal_ids(user)
        all_results: list[SearchResultItem] = []

        with self.db_client.get_session() as session:
            for search_type in search_types:
                config = SEARCH_TYPE_CONFIG[search_type]
                is_admin = self._check_admin_for_type(
                    user, tenant_id, config["admin_roles"]
                )
                type_results = self._search_entity_type(
                    session=session,
                    tenant_id=tenant_id,
                    query=query,
                    config=config,
                    principal_ids=principal_ids,
                    is_admin=is_admin,
                    limit=limit,
                )
                all_results.extend(type_results)

        return SearchResponse(
            results=all_results,
            total=len(all_results),
            query=query,
        )
