from sqlalchemy import and_, select

from unifiedui.caching.client import CacheClient
from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.core.database.enums import PrincipalTypeEnum
from unifiedui.core.database.models import CustomGroupMember, Principal
from unifiedui.core.identity.factory import IdentityProviderFactory, IdentityTokenFactory
from unifiedui.logger import get_logger
from unifiedui.schema.responses.identity import IdentityGroupResponse, IdentityUserResponse
from unifiedui.schema.responses.organizations import OrganizationContextResponse
from unifiedui.utils.api_query import APIFilterQuery

logger = get_logger(__name__)


class ContextIdentityUser:
    def __init__(
        self,
        token: str,
        database_client: SQLAlchemyClient | None = None,
        cache_client: CacheClient | None = None,
        use_cache: bool = True,
    ):
        self.identity = IdentityTokenFactory.create(token)
        self.idp = IdentityProviderFactory.create(self.identity)
        self._use_cache = use_cache
        self._groups: list[IdentityGroupResponse] | None = None
        self._custom_groups: list[IdentityGroupResponse] | None = None
        self._identity_groups: list[IdentityGroupResponse] | None = None
        self._idp_group_ids: list[str] | None = None
        self._tenants: list[dict] | None = None
        self._organization_context: OrganizationContextResponse | None = None
        self._cache = cache_client
        self._database_client = database_client

    def _get_idp_group_ids(self) -> list[str]:
        """Get identity group IDs from the identity provider."""
        if self._idp_group_ids is not None:
            return self._idp_group_ids

        user_id = self.identity.get_id()
        cache_key = f"identity:idp_group_ids:user:{user_id}"

        # Check Redis cache
        if self._use_cache and self._cache:
            try:
                cached_data = self._cache.client.get(cache_key)
                if cached_data is not None:
                    self._idp_group_ids = cached_data
                    logger.debug("Returning cached IDP group IDs for user %s", user_id)
                    return self._idp_group_ids
            except Exception as e:
                logger.warning("Failed to get cached IDP group IDs: %s", e)

        # Fetch from identity provider
        query = APIFilterQuery(top=999)
        idp_groups = self.idp.get_current_user_security_groups(query=query)
        self._idp_group_ids = [g.id for g in idp_groups]
        logger.debug("Fetched %s IDP group IDs from identity provider", len(self._idp_group_ids))

        # Cache the group IDs with 60s TTL
        if self._cache:
            try:
                self._cache.client.set(cache_key, self._idp_group_ids, ttl=60)
                logger.debug("Cached IDP group IDs for user %s (TTL: 60s)", user_id)
            except Exception as e:
                logger.warning("Failed to cache IDP group IDs: %s", e)

        return self._idp_group_ids

    @property
    def groups(self) -> list[IdentityGroupResponse]:
        """
        Get user groups (IDENTITY_GROUP and CUSTOM_GROUP) from the principals table.

        For IDENTITY_GROUP: Fetches groups where the principal_id matches the user's IDP group IDs.
        For CUSTOM_GROUP: Fetches groups where the user is a member via CustomGroupMember table.
        """
        # in-memory cache
        if self._groups is not None:
            return self._groups

        self._groups = []
        user_id = self.identity.get_id()
        cache_key = f"identity:groups:user:{user_id}"

        # Check Redis cache
        if self._use_cache and self._cache:
            try:
                cached_data = self._cache.client.get(cache_key)
                if cached_data is not None:
                    self._groups = [IdentityGroupResponse(**item) for item in cached_data]
                    logger.debug("Returning cached groups for user %s", user_id)
                    return self._groups
            except Exception as e:
                logger.warning("Failed to get cached groups: %s", e)

        if not self._database_client:
            logger.warning("No database client available, returning empty groups list")
            return self._groups

        # Get IDP group IDs from identity provider
        idp_group_ids = self._get_idp_group_ids()

        with self._database_client.get_session() as session:
            # 1. Fetch IDENTITY_GROUPs where user is a member (from IDP)
            if idp_group_ids:
                identity_group_query = select(Principal).where(
                    Principal.principal_type == PrincipalTypeEnum.IDENTITY_GROUP.value,
                    Principal.principal_id.in_(idp_group_ids),
                )
                identity_groups = session.execute(identity_group_query).scalars().all()

                for p in identity_groups:
                    self._groups.append(
                        IdentityGroupResponse(
                            id=p.principal_id,
                            display_name=p.display_name,
                            principal_name=p.principal_name,
                            principal_type=p.principal_type,
                        )
                    )

            # 2. Fetch CUSTOM_GROUPs where user is a member via CustomGroupMember
            custom_group_query = (
                select(Principal)
                .join(
                    CustomGroupMember,
                    and_(
                        CustomGroupMember.tenant_id == Principal.tenant_id,
                        CustomGroupMember.custom_group_id == Principal.principal_id,
                    ),
                )
                .where(
                    Principal.principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value,
                    CustomGroupMember.principal_id == user_id,
                )
            )
            custom_groups = session.execute(custom_group_query).scalars().all()

            for p in custom_groups:
                self._groups.append(
                    IdentityGroupResponse(
                        id=p.principal_id,
                        display_name=p.display_name,
                        principal_name=p.principal_name,
                        principal_type=p.principal_type,
                    )
                )

        logger.debug(
            f"Fetched {len(self._groups)} groups from principals table (identity: {len(idp_group_ids) if idp_group_ids else 0}, custom: {len(custom_groups) if 'custom_groups' in dir() else 0})"
        )

        # Cache the groups with 300s TTL
        if self._cache:
            try:
                groups_data = [g.model_dump() for g in self._groups]
                self._cache.client.set(cache_key, groups_data, ttl=300)
                logger.debug("Cached groups for user %s (TTL: 300s)", user_id)
            except Exception as e:
                logger.warning("Failed to cache groups: %s", e)

        return self._groups

    @property
    def custom_groups(self) -> list[IdentityGroupResponse]:
        """
        Get custom groups the user is a member of (CUSTOM_GROUP only).
        This is a filtered view of the groups property.
        """
        if self._custom_groups is not None:
            return self._custom_groups
        self._custom_groups = [g for g in self.groups if g.principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value]
        return self._custom_groups

    @property
    def identity_groups(self) -> list[IdentityGroupResponse]:
        """
        Get identity groups the user is a member of (IDENTITY_GROUP only).
        This is a filtered view of the groups property.
        """
        if self._identity_groups is not None:
            return self._identity_groups
        self._identity_groups = [g for g in self.groups if g.principal_type == PrincipalTypeEnum.IDENTITY_GROUP.value]
        return self._identity_groups

    @property
    def tenants(self) -> list[dict]:
        """
        Get all tenants the user has access to with their roles.
        Returns list of dicts with 'tenant' and 'roles' keys.
        Roles are deduplicated across IDENTITY_USER, IDENTITY_GROUP, and CUSTOM_GROUP.
        """
        # in-memory cache
        if self._tenants is not None:
            return self._tenants

        self._tenants = []

        if not self._database_client:
            return self._tenants

        # Get user ID and group IDs
        user_id = self.identity.get_id()
        # Get IDP group IDs from identity provider (not from groups property to avoid circular dependency)
        idp_group_ids = self._get_idp_group_ids()
        # Get custom group IDs from groups property (filter by CUSTOM_GROUP type)
        custom_group_ids = [g.id for g in self.groups if g.principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value]

        # Use TenantHandler to get tenants with roles (caching is handled in the handler)
        db_client = self._database_client
        if not db_client:
            from unifiedui.handlers.dependencies import get_db_client

            db_client = get_db_client()

        from unifiedui.handlers.tenants import TenantHandler

        handler = TenantHandler(db_client, self._cache)

        self._tenants = handler.get_user_tenants_with_permissions(
            user_id=user_id,
            identity_group_ids=idp_group_ids,
            custom_group_ids=custom_group_ids,
            use_cache=self._use_cache,
        )

        logger.debug("Fetched %s tenants with permissions for user %s", len(self._tenants), user_id)

        return self._tenants

    @property
    def organization_context(self) -> OrganizationContextResponse | None:
        """Get the organization context for the current user based on IDP tenant."""
        if self._organization_context is not None:
            return self._organization_context

        if not self._database_client:
            return None

        identity_provider = self.identity.get_identity_provider()
        identity_tenant_id = self.identity.get_identity_tenant_id()

        if not identity_provider or not identity_tenant_id:
            return None

        from unifiedui.handlers.organizations import OrganizationHandler

        handler = OrganizationHandler(self._database_client, self._cache)
        user_id = self.identity.get_id()
        idp_group_ids = self._get_idp_group_ids()

        self._organization_context = handler.get_user_organization_context(
            identity_provider=identity_provider,
            identity_tenant_id=identity_tenant_id,
            user_id=user_id,
            identity_group_ids=idp_group_ids,
        )

        return self._organization_context

    def get_me(self) -> IdentityUserResponse:
        """Get the current user's identity information.

        If the user is a system admin with an organization but no roles,
        they are automatically enrolled as ORGANISATION_GLOBAL_ADMIN.
        """
        from unifiedui.core.config import settings

        org_context = self.organization_context
        tenants_with_permissions = self.tenants

        user_mail = self.identity.get_mail()
        user_principal = self.identity.get_principal_name()

        email_match = bool(
            settings.system_admin_email
            and user_mail
            and user_mail.lower().strip() == settings.system_admin_email.lower().strip()
        )
        username_match = bool(
            settings.system_admin_username
            and user_principal
            and user_principal.lower().strip() == settings.system_admin_username.lower().strip()
        )
        is_system_admin = email_match or username_match

        if is_system_admin and org_context and not org_context.roles:
            org_context = self._auto_enroll_system_admin(org_context)

        return IdentityUserResponse(
            id=self.identity.get_id(),
            identity_provider=self.identity.get_identity_provider(),
            identity_tenant_id=self.identity.get_identity_tenant_id(),
            display_name=self.identity.get_display_name(),
            principal_name=self.identity.get_principal_name(),
            mail=user_mail,
            firstname=self.identity.get_firstname(),
            lastname=self.identity.get_lastname(),
            is_system_admin=is_system_admin,
            organization=org_context,
            tenants=tenants_with_permissions,
            groups=self.groups,
        )

    def _auto_enroll_system_admin(
        self,
        org_context: OrganizationContextResponse,
    ) -> OrganizationContextResponse:
        """Auto-enroll a system admin as ORGANISATION_GLOBAL_ADMIN.

        When a system admin sees an organization (via IDP match) but has
        no roles, they are automatically added as a member so they can
        manage the organization.

        Args:
            org_context: The matched organization context with empty roles.

        Returns:
            Updated organization context with the admin role assigned.
        """
        import uuid

        from unifiedui.core.database.enums import OrganizationRoleEnum
        from unifiedui.core.database.models import OrganizationMember

        if not self._database_client:
            return org_context

        user_id = self.identity.get_id()
        role = OrganizationRoleEnum.ORGANISATION_GLOBAL_ADMIN.value

        with self._database_client.get_session() as session:
            member = OrganizationMember(
                id=str(uuid.uuid4()),
                organization_id=org_context.id,
                principal_id=user_id,
                principal_type=PrincipalTypeEnum.IDENTITY_USER.value,
                role=role,
                created_by=user_id,
                updated_by=user_id,
            )
            session.add(member)
            session.commit()

        logger.info("Auto-enrolled system admin %s as %s in org %s", user_id, role, org_context.id)

        return OrganizationContextResponse(
            id=org_context.id,
            name=org_context.name,
            slug=org_context.slug,
            roles=[role],
        )
