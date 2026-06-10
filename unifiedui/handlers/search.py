"""Business logic handlers for global search operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import String, func, literal, or_, select, union_all
from sqlalchemy import cast as sql_cast

from unifiedui.core.database.enums import PrincipalTypeEnum, TenantRolesEnum
from unifiedui.core.database.models import (
    ChatAgent,
    ChatAgentMember,
    ChatAgentTag,
    ChatWidget,
    ChatWidgetMember,
    ChatWidgetTag,
    Conversation,
    ConversationMember,
    Credential,
    CredentialMember,
    CredentialTag,
    ExternalApp,
    ExternalAppMember,
    ExternalAppTag,
    Principal,
    Tag,
    TenantAIModel,
    TenantAIModelTag,
    Workflow,
    WorkflowMember,
    WorkflowTag,
)

if TYPE_CHECKING:
    from unifiedui.caching.client import CacheClient
    from unifiedui.core.database.client import SQLAlchemyClient
    from unifiedui.core.identity.users import ContextIdentityUser

from unifiedui.logger import get_logger
from unifiedui.schema.responses.search import SearchResponse, SearchResultItem

logger = get_logger(__name__)

VALID_SEARCH_TYPES = {
    "chat_agent",
    "workflow",
    "conversation",
    "chat_widget",
    "external_app",
    "credential",
    "tenant_ai_model",
    "principal",
    "custom_group",
}

MEMBER_SEARCH_TYPE_CONFIG = {
    "chat_agent": {
        "entity_model": ChatAgent,
        "member_model": ChatAgentMember,
        "entity_id_field": "chat_agent_id",
        "tag_model": ChatAgentTag,
        "tag_entity_id_field": "chat_agent_id",
        "admin_roles": [
            TenantRolesEnum.TENANT_GLOBAL_ADMIN,
            TenantRolesEnum.CHAT_AGENTS_ADMIN,
        ],
    },
    "workflow": {
        "entity_model": Workflow,
        "member_model": WorkflowMember,
        "entity_id_field": "workflow_id",
        "tag_model": WorkflowTag,
        "tag_entity_id_field": "workflow_id",
        "admin_roles": [
            TenantRolesEnum.TENANT_GLOBAL_ADMIN,
            TenantRolesEnum.WORKFLOWS_ADMIN,
        ],
    },
    "conversation": {
        "entity_model": Conversation,
        "member_model": ConversationMember,
        "entity_id_field": "conversation_id",
        "tag_model": None,
        "tag_entity_id_field": None,
        "admin_roles": [
            TenantRolesEnum.TENANT_GLOBAL_ADMIN,
            TenantRolesEnum.CONVERSATIONS_ADMIN,
        ],
    },
    "chat_widget": {
        "entity_model": ChatWidget,
        "member_model": ChatWidgetMember,
        "entity_id_field": "chat_widget_id",
        "tag_model": ChatWidgetTag,
        "tag_entity_id_field": "chat_widget_id",
        "admin_roles": [
            TenantRolesEnum.TENANT_GLOBAL_ADMIN,
            TenantRolesEnum.CHAT_WIDGETS_ADMIN,
        ],
    },
    "external_app": {
        "entity_model": ExternalApp,
        "member_model": ExternalAppMember,
        "entity_id_field": "external_app_id",
        "tag_model": ExternalAppTag,
        "tag_entity_id_field": "external_app_id",
        "admin_roles": [
            TenantRolesEnum.TENANT_GLOBAL_ADMIN,
            TenantRolesEnum.EXTERNAL_APPS_ADMIN,
        ],
    },
    "credential": {
        "entity_model": Credential,
        "member_model": CredentialMember,
        "entity_id_field": "credential_id",
        "tag_model": CredentialTag,
        "tag_entity_id_field": "credential_id",
        "admin_roles": [
            TenantRolesEnum.TENANT_GLOBAL_ADMIN,
            TenantRolesEnum.CREDENTIALS_ADMIN,
        ],
    },
}

TENANT_SCOPED_SEARCH_TYPE_CONFIG = {
    "tenant_ai_model": {
        "entity_model": TenantAIModel,
        "tag_model": TenantAIModelTag,
        "tag_entity_id_field": "tenant_ai_model_id",
        "admin_roles": [
            TenantRolesEnum.TENANT_GLOBAL_ADMIN,
            TenantRolesEnum.TENANT_AI_MODELS_ADMIN,
        ],
    },
}


class SearchHandler:
    """Handler class for global search business logic."""

    def __init__(
        self,
        db_client: SQLAlchemyClient,
        cache_client: CacheClient | None = None,
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
        identity_group_ids = [g.id for g in user.groups if g.principal_type == PrincipalTypeEnum.IDENTITY_GROUP.value]
        custom_group_ids = [g.id for g in user.groups if g.principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value]
        return [user_id, *identity_group_ids, *custom_group_ids]

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

    def _build_member_subquery(
        self,
        search_type: str,
        config: dict,
        tenant_id: str,
        like_pattern: str,
        principal_ids: list[str],
        is_admin: bool,
    ):
        """Build a SELECT subquery for a member-based entity type.

        Args:
            search_type: Entity type key.
            config: Search type configuration dict.
            tenant_id: Tenant scope.
            like_pattern: LIKE pattern for search.
            principal_ids: User principal IDs for filtering.
            is_admin: Whether user is admin for this type.

        Returns:
            SQLAlchemy SELECT statement or None if no access.
        """
        entity_model = config["entity_model"]
        member_model = config["member_model"]
        entity_id_field = config["entity_id_field"]

        has_type_col = search_type in ("chat_agent", "chat_widget")

        base_filters = [
            entity_model.tenant_id == tenant_id,
            or_(
                entity_model.name.ilike(like_pattern),
                entity_model.description.ilike(like_pattern),
            ),
        ]

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

        sub_type_col = sql_cast(entity_model.type, String) if has_type_col else literal(None)

        if search_type == "conversation":
            return (
                select(
                    literal(search_type).label("entity_type"),
                    entity_model.id.label("entity_id"),
                    entity_model.name.label("entity_name"),
                    entity_model.description.label("entity_description"),
                    sub_type_col.label("sub_type"),
                    ChatAgent.name.label("subtitle"),
                )
                .outerjoin(ChatAgent, entity_model.chat_agent_id == ChatAgent.id)
                .where(*base_filters)
            )

        return select(
            literal(search_type).label("entity_type"),
            entity_model.id.label("entity_id"),
            entity_model.name.label("entity_name"),
            entity_model.description.label("entity_description"),
            sub_type_col.label("sub_type"),
            literal(None).label("subtitle"),
        ).where(*base_filters)

    def _build_tenant_scoped_subquery(
        self,
        search_type: str,
        config: dict,
        tenant_id: str,
        like_pattern: str,
    ):
        """Build a SELECT subquery for a tenant-scoped entity type.

        Args:
            search_type: Entity type key.
            config: Search type configuration dict.
            tenant_id: Tenant scope.
            like_pattern: LIKE pattern for search.

        Returns:
            SQLAlchemy SELECT statement.
        """
        entity_model = config["entity_model"]

        return select(
            literal(search_type).label("entity_type"),
            entity_model.id.label("entity_id"),
            entity_model.name.label("entity_name"),
            entity_model.description.label("entity_description"),
            literal(None).label("sub_type"),
            literal(None).label("subtitle"),
        ).where(
            entity_model.tenant_id == tenant_id,
            or_(
                entity_model.name.ilike(like_pattern),
                entity_model.description.ilike(like_pattern),
            ),
        )

    def _build_principal_subquery(
        self,
        search_type: str,
        principal_type: PrincipalTypeEnum,
        tenant_id: str,
        like_pattern: str,
    ):
        """Build a SELECT subquery for principals.

        Args:
            search_type: Entity type key.
            principal_type: Principal type filter.
            tenant_id: Tenant scope.
            like_pattern: LIKE pattern for search.

        Returns:
            SQLAlchemy SELECT statement.
        """
        return select(
            literal(search_type).label("entity_type"),
            Principal.principal_id.label("entity_id"),
            Principal.display_name.label("entity_name"),
            Principal.description.label("entity_description"),
            literal(None).label("sub_type"),
            literal(None).label("subtitle"),
        ).where(
            Principal.tenant_id == tenant_id,
            Principal.principal_type == principal_type.value,
            or_(
                Principal.display_name.ilike(like_pattern),
                Principal.description.ilike(like_pattern),
                Principal.mail.ilike(like_pattern),
            ),
        )

    def search(
        self,
        tenant_id: str,
        user: ContextIdentityUser,
        query: str,
        types: list[str] | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> SearchResponse:
        """Execute global search across entity types using a single UNION ALL query.

        Args:
            tenant_id: Tenant ID for scoping.
            user: Authenticated user context.
            query: Search query string.
            types: Entity types to search (None = all).
            limit: Maximum results.
            offset: Number of results to skip.

        Returns:
            Search response with results.
        """
        if not query or not query.strip():
            return SearchResponse(results=[], total=0, query=query or "")

        query = query.strip()
        like_pattern = f"%{query}%"

        search_types = VALID_SEARCH_TYPES
        if types:
            search_types = VALID_SEARCH_TYPES & set(types)

        if not search_types:
            return SearchResponse(results=[], total=0, query=query)

        principal_ids = self._get_principal_ids(user)

        principal_search_types = {"principal", "custom_group"}
        principal_type_map = {
            "principal": PrincipalTypeEnum.IDENTITY_USER,
            "custom_group": PrincipalTypeEnum.CUSTOM_GROUP,
        }
        principal_admin_roles: dict[str, list[TenantRolesEnum]] = {
            "principal": [TenantRolesEnum.TENANT_GLOBAL_ADMIN],
            "custom_group": [
                TenantRolesEnum.TENANT_GLOBAL_ADMIN,
                TenantRolesEnum.CUSTOM_GROUPS_ADMIN,
            ],
        }

        subqueries: list[Any] = []
        active_type_configs: dict[str, dict[str, Any]] = {}

        for search_type in search_types:
            if search_type in MEMBER_SEARCH_TYPE_CONFIG:
                config = MEMBER_SEARCH_TYPE_CONFIG[search_type]
                is_admin = self._check_admin_for_type(
                    user, tenant_id, cast("list[TenantRolesEnum]", config["admin_roles"])
                )
                subq = self._build_member_subquery(
                    search_type=search_type,
                    config=config,
                    tenant_id=tenant_id,
                    like_pattern=like_pattern,
                    principal_ids=principal_ids,
                    is_admin=is_admin,
                )
                subqueries.append(subq)
                active_type_configs[search_type] = config

            elif search_type in TENANT_SCOPED_SEARCH_TYPE_CONFIG:
                config = TENANT_SCOPED_SEARCH_TYPE_CONFIG[search_type]
                is_admin = self._check_admin_for_type(
                    user, tenant_id, cast("list[TenantRolesEnum]", config["admin_roles"])
                )
                if not is_admin:
                    continue
                subq = self._build_tenant_scoped_subquery(
                    search_type=search_type,
                    config=config,
                    tenant_id=tenant_id,
                    like_pattern=like_pattern,
                )
                subqueries.append(subq)
                active_type_configs[search_type] = config

            elif search_type in principal_search_types:
                admin_roles = principal_admin_roles[search_type]
                is_admin = self._check_admin_for_type(user, tenant_id, admin_roles)
                if not is_admin:
                    continue
                subq = self._build_principal_subquery(
                    search_type=search_type,
                    principal_type=principal_type_map[search_type],
                    tenant_id=tenant_id,
                    like_pattern=like_pattern,
                )
                subqueries.append(subq)

        if not subqueries:
            return SearchResponse(results=[], total=0, query=query)

        combined_query = union_all(*subqueries).subquery()

        count_query = select(func.count()).select_from(combined_query)

        paginated_query = select(combined_query).order_by(combined_query.c.entity_name).offset(offset).limit(limit)

        with self.db_client.get_session() as session:
            total = session.execute(count_query).scalar() or 0
            rows = session.execute(paginated_query).all()

            entity_ids_by_type: dict[str, list[str]] = {}
            for row in rows:
                entity_type = row.entity_type
                entity_ids_by_type.setdefault(entity_type, []).append(row.entity_id)

            tags_map: dict[str, dict[str, list[str]]] = {}
            for entity_type, entity_ids in entity_ids_by_type.items():
                type_config = active_type_configs.get(entity_type)
                if not type_config or not type_config.get("tag_model"):
                    continue
                tag_entity_id_field = cast("str", type_config["tag_entity_id_field"])
                type_tags = self._load_tags_for_entities(
                    session,
                    tenant_id,
                    type_config["tag_model"],
                    tag_entity_id_field,
                    entity_ids,
                )
                tags_map[entity_type] = type_tags

            results: list[SearchResultItem] = []
            for row in rows:
                entity_type = row.entity_type
                entity_id = row.entity_id
                name = row.entity_name
                description = row.entity_description
                sub_type = row.sub_type
                subtitle = row.subtitle

                match_field = "name" if query.lower() in (name or "").lower() else "description"
                entity_tags = tags_map.get(entity_type, {}).get(entity_id, [])

                results.append(
                    SearchResultItem(
                        type=entity_type,
                        id=entity_id,
                        name=name,
                        description=description,
                        subtitle=subtitle,
                        match_field=match_field,
                        is_active=None,
                        tags=entity_tags,
                        sub_type=sub_type,
                    )
                )

        return SearchResponse(
            results=results,
            total=total,
            query=query,
        )
