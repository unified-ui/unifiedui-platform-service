"""Business logic handlers for dashboard operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from unifiedui.core.database.enums import TenantRolesEnum
from unifiedui.core.database.models import (
    AutonomousAgent,
    AutonomousAgentMember,
    ChatAgent,
    ChatAgentMember,
    Conversation,
    ConversationMember,
)

if TYPE_CHECKING:
    from unifiedui.caching.client import CacheClient
    from unifiedui.core.database.client import SQLAlchemyClient
    from unifiedui.core.identity.users import ContextIdentityUser

from unifiedui.logger import get_logger
from unifiedui.schema.responses.dashboard import DashboardStatsResponse, EntityStatsResponse

logger = get_logger(__name__)


class DashboardHandler:
    """Handler class for dashboard business logic."""

    def __init__(
        self,
        db_client: SQLAlchemyClient,
        cache_client: CacheClient | None = None,
    ):
        """Initialize the dashboard handler.

        Args:
            db_client: Database client for queries.
            cache_client: Optional cache client for response caching.
        """
        self.db_client = db_client
        self.cache_client = cache_client

    def _check_tenant_admin(
        self,
        user: ContextIdentityUser,
        tenant_id: str,
        admin_roles: list[TenantRolesEnum],
    ) -> bool:
        """Check if user has tenant admin roles.

        Args:
            user: Authenticated user context.
            tenant_id: Tenant ID to check.
            admin_roles: List of admin roles to check.

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

    def _count_entity_with_permissions(
        self,
        tenant_id: str,
        user: ContextIdentityUser,
        entity_model: type,
        member_model: type,
        entity_id_field: str,
        is_admin: bool,
        has_active_field: bool = True,
    ) -> EntityStatsResponse:
        """Count entities respecting permission filtering.

        Args:
            tenant_id: Tenant scope.
            user: Authenticated user for permission filtering.
            entity_model: SQLAlchemy model class for the entity.
            member_model: SQLAlchemy model class for the member table.
            entity_id_field: Field name of entity FK on member model.
            is_admin: Whether user is tenant admin (skip member filtering).
            has_active_field: Whether entity has is_active field.

        Returns:
            Entity stats with total, active, inactive counts.
        """
        with self.db_client.get_session() as session:
            base_filter = [entity_model.tenant_id == tenant_id]

            if not is_admin:
                user_id = user.identity.get_id()
                identity_group_ids = [g.id for g in user.groups]
                custom_group_ids = [g.id for g in user.custom_groups]
                principal_ids = [user_id, *identity_group_ids, *custom_group_ids]

                member_subquery = (
                    select(getattr(member_model, entity_id_field))
                    .where(
                        member_model.tenant_id == tenant_id,
                        member_model.principal_id.in_(principal_ids),
                    )
                    .distinct()
                )
                base_filter.append(entity_model.id.in_(member_subquery))

            total_query = select(func.count(entity_model.id)).where(*base_filter)
            total = session.execute(total_query).scalar() or 0

            if has_active_field:
                active_query = select(func.count(entity_model.id)).where(*base_filter, entity_model.is_active.is_(True))
                active = session.execute(active_query).scalar() or 0
                inactive = total - active
            else:
                active = total
                inactive = 0

            return EntityStatsResponse(total=total, active=active, inactive=inactive)

    def get_dashboard_stats(
        self,
        tenant_id: str,
        user: ContextIdentityUser,
        use_cache: bool = True,
    ) -> DashboardStatsResponse:
        """Get dashboard statistics for the tenant.

        Args:
            tenant_id: Tenant ID for scoping.
            user: Authenticated user context.
            use_cache: Whether to use cached results.

        Returns:
            Dashboard stats with counts per entity type.
        """
        user_id = user.identity.get_id()
        cache_key = f"dashboard:stats:tenant:{tenant_id}:user:{user_id}"

        if use_cache and self.cache_client:
            cached = self.cache_client.client.get(cache_key)
            if cached:
                return DashboardStatsResponse(**cached)

        is_admin = self._check_tenant_admin(
            user,
            tenant_id,
            [
                TenantRolesEnum.GLOBAL_ADMIN,
            ],
        )

        chat_agents = self._count_entity_with_permissions(
            tenant_id=tenant_id,
            user=user,
            entity_model=ChatAgent,
            member_model=ChatAgentMember,
            entity_id_field="chat_agent_id",
            is_admin=is_admin,
            has_active_field=True,
        )

        autonomous_agents = self._count_entity_with_permissions(
            tenant_id=tenant_id,
            user=user,
            entity_model=AutonomousAgent,
            member_model=AutonomousAgentMember,
            entity_id_field="autonomous_agent_id",
            is_admin=is_admin,
            has_active_field=True,
        )

        conversations = self._count_entity_with_permissions(
            tenant_id=tenant_id,
            user=user,
            entity_model=Conversation,
            member_model=ConversationMember,
            entity_id_field="conversation_id",
            is_admin=is_admin,
            has_active_field=False,
        )

        result = DashboardStatsResponse(
            chat_agents=chat_agents,
            autonomous_agents=autonomous_agents,
            conversations=conversations,
        )

        if self.cache_client:
            self.cache_client.client.set(cache_key, result.model_dump(), ttl=120)

        return result
