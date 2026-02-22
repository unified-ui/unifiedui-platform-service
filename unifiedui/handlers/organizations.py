"""Business logic handlers for organization operations."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from unifiedui.core.database.enums import EnvironmentTypeEnum, OrganizationRoleEnum
from unifiedui.core.database.models import (
    Organization,
    OrganizationMember,
    Tenant,
    TenantMember,
)
from unifiedui.exc.organizations import (
    OrganizationAlreadyExistsError,
    OrganizationMemberAlreadyExistsError,
    OrganizationMemberNotFoundError,
    OrganizationNotFoundError,
    OrganizationSlugAlreadyExistsError,
    TenantCannotBeDeletedError,
)
from unifiedui.handlers.principals_helper import ensure_principal_exists
from unifiedui.logger import get_logger
from unifiedui.schema.responses.organizations import (
    OrganizationContextResponse,
    OrganizationMemberResponse,
    OrganizationMemberRoleResponse,
    OrganizationMembersResponse,
    OrganizationResponse,
    TenantWithOrganizationResponse,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from unifiedui.caching.client import CacheClient
    from unifiedui.core.database.client import SQLAlchemyClient
    from unifiedui.core.identity.users import ContextIdentityUser
    from unifiedui.schema.requests.organizations import (
        CreateOrganizationRequest,
        CreateTenantInOrganizationRequest,
        DeleteOrganizationMemberRequest,
        SetOrganizationMemberRequest,
        UpdateOrganizationRequest,
    )

logger = get_logger(__name__)


class OrganizationHandler:
    """Handler class for organization business logic."""

    def __init__(self, db_client: SQLAlchemyClient, cache_client: CacheClient | None = None):
        self.db_client = db_client
        self.cache_client = cache_client

    def get_organization(self, organization_id: str) -> OrganizationResponse:
        """Get a specific organization by ID."""
        logger.info("Fetching organization", extra={"organization_id": organization_id})

        with self.db_client.get_session() as session:
            org = self._validate_organization_exists(session, organization_id)
            return self._org_to_response(org)

    def get_organization_by_idp(self, identity_provider: str, identity_tenant_id: str) -> OrganizationResponse | None:
        """Get organization by identity provider and tenant ID."""
        logger.info(
            "Fetching organization by IDP",
            extra={"identity_provider": identity_provider, "identity_tenant_id": identity_tenant_id},
        )

        with self.db_client.get_session() as session:
            org = session.execute(
                select(Organization).where(
                    Organization.identity_provider == identity_provider,
                    Organization.identity_tenant_id == identity_tenant_id,
                )
            ).scalar_one_or_none()

            if org is None:
                return None
            return self._org_to_response(org)

    def create_organization(
        self,
        request: CreateOrganizationRequest,
        user_id: str,
        user: ContextIdentityUser | None = None,
        create_default_tenant: bool = True,
    ) -> OrganizationResponse:
        """Create a new organization, optionally with a default tenant."""
        logger.info("Creating organization", extra={"org_name": request.name, "user_id": user_id})

        organization_id = str(uuid.uuid4())

        with self.db_client.get_session() as session:
            org = Organization(
                id=organization_id,
                name=request.name,
                slug=request.slug,
                description=request.description,
                identity_provider=request.identity_provider,
                identity_tenant_id=request.identity_tenant_id,
                subscription_tier=request.subscription_tier,
                is_active=True,
                created_by=user_id,
                updated_by=user_id,
            )
            session.add(org)

            try:
                session.flush()
            except IntegrityError as e:
                session.rollback()
                error_str = str(e)
                if "uq_org_idp" in error_str:
                    raise OrganizationAlreadyExistsError(request.identity_tenant_id) from e
                if "slug" in error_str.lower():
                    raise OrganizationSlugAlreadyExistsError(request.slug) from e
                raise

            if create_default_tenant:
                # Create default tenant
                default_tenant_id = str(uuid.uuid4())
                default_tenant = Tenant(
                    id=default_tenant_id,
                    name="Default",
                    description="Default tenant",
                    organization_id=organization_id,
                    environment_type=EnvironmentTypeEnum.SANDBOX.value,
                    is_default=True,
                    can_be_deleted=False,
                    created_by=user_id,
                    updated_by=user_id,
                )
                session.add(default_tenant)
                session.flush()

                # Ensure principal exists for the creator
                if user is not None:
                    ensure_principal_exists(
                        session=session,
                        tenant_id=default_tenant_id,
                        principal_id=user_id,
                        principal_type="IDENTITY_USER",
                        user=user,
                    )

                # Assign creator as TENANT_GLOBAL_ADMIN on the default tenant
                tenant_role = TenantMember(
                    id=str(uuid.uuid4()),
                    tenant_id=default_tenant_id,
                    principal_id=user_id,
                    role="TENANT_GLOBAL_ADMIN",
                    created_by=user_id,
                    updated_by=user_id,
                )
                session.add(tenant_role)

            # Assign creator as ORGANISATION_GLOBAL_ADMIN
            org_member = OrganizationMember(
                id=str(uuid.uuid4()),
                organization_id=organization_id,
                principal_id=user_id,
                principal_type="IDENTITY_USER",
                role=OrganizationRoleEnum.ORGANISATION_GLOBAL_ADMIN.value,
                created_by=user_id,
                updated_by=user_id,
            )
            session.add(org_member)
            session.flush()

            logger.info(
                "Organization created",
                extra={
                    "organization_id": organization_id,
                    "with_default_tenant": create_default_tenant,
                    "user_id": user_id,
                },
            )

            return self._org_to_response(org)

    def update_organization(
        self, organization_id: str, request: UpdateOrganizationRequest, user_id: str
    ) -> OrganizationResponse:
        """Update an existing organization."""
        logger.info("Updating organization", extra={"organization_id": organization_id, "user_id": user_id})

        with self.db_client.get_session() as session:
            org = self._validate_organization_exists(session, organization_id)

            if request.name is not None:
                org.name = request.name
            if request.description is not None:
                org.description = request.description
            if request.subscription_tier is not None:
                org.subscription_tier = request.subscription_tier
            if request.is_active is not None:
                org.is_active = request.is_active

            org.updated_by = user_id

            logger.info("Organization updated", extra={"organization_id": organization_id})
            return self._org_to_response(org)

    # ---------- Organization Members ----------

    def list_members(self, organization_id: str) -> OrganizationMembersResponse:
        """List all members of an organization."""
        logger.info("Listing organization members", extra={"organization_id": organization_id})

        with self.db_client.get_session() as session:
            self._validate_organization_exists(session, organization_id)

            members = (
                session.execute(
                    select(OrganizationMember)
                    .where(OrganizationMember.organization_id == organization_id)
                    .order_by(OrganizationMember.principal_id, OrganizationMember.role)
                )
                .scalars()
                .all()
            )

            # Group by principal_id
            members_dict: dict[str, list[OrganizationMember]] = {}
            for member in members:
                if member.principal_id not in members_dict:
                    members_dict[member.principal_id] = []
                members_dict[member.principal_id].append(member)

            member_responses = []
            for principal_id, member_roles in members_dict.items():
                first = member_roles[0]
                member_responses.append(
                    OrganizationMemberResponse(
                        principal_id=principal_id,
                        principal_type=first.principal_type,
                        display_name=None,
                        principal_name=None,
                        mail=None,
                        roles=[
                            OrganizationMemberRoleResponse(
                                id=m.id,
                                principal_id=m.principal_id,
                                principal_type=m.principal_type,
                                role=m.role,
                                created_at=m.created_at,
                            )
                            for m in member_roles
                        ],
                    )
                )

            return OrganizationMembersResponse(
                organization_id=organization_id,
                members=member_responses,
            )

    def set_member(
        self,
        organization_id: str,
        request: SetOrganizationMemberRequest,
        user_id: str,
    ) -> OrganizationMemberRoleResponse:
        """Add or set a member role in the organization."""
        logger.info(
            "Setting organization member",
            extra={
                "organization_id": organization_id,
                "principal_id": request.principal_id,
                "role": request.role,
            },
        )

        with self.db_client.get_session() as session:
            self._validate_organization_exists(session, organization_id)

            # Check if member already has this role
            existing = session.execute(
                select(OrganizationMember).where(
                    OrganizationMember.organization_id == organization_id,
                    OrganizationMember.principal_id == request.principal_id,
                    OrganizationMember.role == request.role,
                )
            ).scalar_one_or_none()

            if existing:
                raise OrganizationMemberAlreadyExistsError(request.principal_id, request.role)

            member = OrganizationMember(
                id=str(uuid.uuid4()),
                organization_id=organization_id,
                principal_id=request.principal_id,
                principal_type=request.principal_type,
                role=request.role,
                created_by=user_id,
                updated_by=user_id,
            )
            session.add(member)
            session.flush()

            logger.info(
                "Organization member role set",
                extra={"member_id": member.id, "role": request.role},
            )

            return OrganizationMemberRoleResponse(
                id=member.id,
                principal_id=member.principal_id,
                principal_type=member.principal_type,
                role=member.role,
                created_at=member.created_at,
            )

    def delete_member(
        self,
        organization_id: str,
        request: DeleteOrganizationMemberRequest,
    ) -> None:
        """Remove a member role from the organization."""
        logger.info(
            "Deleting organization member role",
            extra={
                "organization_id": organization_id,
                "principal_id": request.principal_id,
                "role": request.role,
            },
        )

        with self.db_client.get_session() as session:
            self._validate_organization_exists(session, organization_id)

            member = session.execute(
                select(OrganizationMember).where(
                    OrganizationMember.organization_id == organization_id,
                    OrganizationMember.principal_id == request.principal_id,
                    OrganizationMember.role == request.role,
                )
            ).scalar_one_or_none()

            if not member:
                raise OrganizationMemberNotFoundError(request.principal_id)

            session.delete(member)
            logger.info("Organization member role deleted")

    # ---------- Organization Tenants ----------

    def list_tenants(self, organization_id: str) -> list[TenantWithOrganizationResponse]:
        """List all tenants in an organization."""
        logger.info("Listing organization tenants", extra={"organization_id": organization_id})

        with self.db_client.get_session() as session:
            self._validate_organization_exists(session, organization_id)

            tenants = (
                session.execute(select(Tenant).where(Tenant.organization_id == organization_id).order_by(Tenant.name))
                .scalars()
                .all()
            )

            return [self._tenant_to_extended_response(t) for t in tenants]

    def create_tenant(
        self,
        organization_id: str,
        request: CreateTenantInOrganizationRequest,
        user_id: str,
        user: ContextIdentityUser,
    ) -> TenantWithOrganizationResponse:
        """Create a new tenant within an organization."""
        logger.info(
            "Creating tenant in organization",
            extra={"organization_id": organization_id, "tenant_name": request.name},
        )

        with self.db_client.get_session() as session:
            self._validate_organization_exists(session, organization_id)

            tenant_id = str(uuid.uuid4())
            tenant = Tenant(
                id=tenant_id,
                name=request.name,
                description=request.description,
                organization_id=organization_id,
                environment_type=request.environment_type,
                previous_stage_id=request.previous_stage_id,
                is_default=request.is_default,
                can_be_deleted=not request.is_default,
                created_by=user_id,
                updated_by=user_id,
            )
            session.add(tenant)
            session.flush()

            # Ensure principal exists and assign TENANT_GLOBAL_ADMIN on the new tenant
            ensure_principal_exists(
                session=session,
                tenant_id=tenant_id,
                principal_id=user_id,
                principal_type="IDENTITY_USER",
                user=user,
            )

            tenant_role = TenantMember(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                principal_id=user_id,
                role="TENANT_GLOBAL_ADMIN",
                created_by=user_id,
                updated_by=user_id,
            )
            session.add(tenant_role)
            session.flush()

            logger.info(
                "Tenant created in organization",
                extra={"tenant_id": tenant_id, "organization_id": organization_id},
            )

            # Invalidate caches
            self._invalidate_caches(user_id)

            return self._tenant_to_extended_response(tenant)

    def delete_tenant_in_organization(self, organization_id: str, tenant_id: str) -> None:
        """Delete a tenant within an organization (respecting can_be_deleted flag)."""
        logger.info(
            "Deleting tenant in organization",
            extra={"organization_id": organization_id, "tenant_id": tenant_id},
        )

        with self.db_client.get_session() as session:
            self._validate_organization_exists(session, organization_id)

            tenant = session.get(Tenant, tenant_id)
            if not tenant or tenant.organization_id != organization_id:
                from unifiedui.exc.tenants import TenantNotFoundError

                raise TenantNotFoundError(tenant_id)

            if not tenant.can_be_deleted:
                raise TenantCannotBeDeletedError(tenant_id)

            session.delete(tenant)
            logger.info("Tenant deleted from organization", extra={"tenant_id": tenant_id})

            self._invalidate_caches()

    # ---------- User Organization Context ----------

    def get_user_organization_context(
        self,
        identity_provider: str,
        identity_tenant_id: str,
        user_id: str,
        identity_group_ids: list[str],
    ) -> OrganizationContextResponse | None:
        """Get the organization context for a user based on their IDP tenant."""
        with self.db_client.get_session() as session:
            org = session.execute(
                select(Organization).where(
                    Organization.identity_provider == identity_provider,
                    Organization.identity_tenant_id == identity_tenant_id,
                )
            ).scalar_one_or_none()

            if org is None:
                return None

            # Get user's org roles (direct + via groups)
            all_principal_ids = [user_id, *identity_group_ids]
            members = (
                session.execute(
                    select(OrganizationMember).where(
                        OrganizationMember.organization_id == org.id,
                        OrganizationMember.principal_id.in_(all_principal_ids),
                    )
                )
                .scalars()
                .all()
            )

            roles = sorted({m.role for m in members})

            return OrganizationContextResponse(
                id=org.id,
                name=org.name,
                slug=org.slug,
                roles=roles,
            )

    # ---------- Private Helpers ----------

    def _validate_organization_exists(self, session: Session, organization_id: str) -> Organization:
        """Validate that an organization exists and return it."""
        org = session.get(Organization, organization_id)
        if not org:
            raise OrganizationNotFoundError(organization_id)
        return org

    @staticmethod
    def _org_to_response(org: Organization) -> OrganizationResponse:
        """Convert an Organization model to a response."""
        return OrganizationResponse(
            id=org.id,
            name=org.name,
            slug=org.slug,
            description=org.description,
            identity_provider=org.identity_provider,
            identity_tenant_id=org.identity_tenant_id,
            subscription_tier=org.subscription_tier,
            is_active=org.is_active,
            created_at=org.created_at,
            updated_at=org.updated_at,
            created_by=org.created_by,
            updated_by=org.updated_by,
        )

    @staticmethod
    def _tenant_to_extended_response(tenant: Tenant) -> TenantWithOrganizationResponse:
        """Convert a Tenant model to an extended response with organization fields."""
        return TenantWithOrganizationResponse(
            id=tenant.id,
            name=tenant.name,
            description=tenant.description,
            organization_id=tenant.organization_id,
            environment_type=tenant.environment_type,
            previous_stage_id=tenant.previous_stage_id,
            is_default=tenant.is_default,
            can_be_deleted=tenant.can_be_deleted,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
            created_by=tenant.created_by,
            updated_by=tenant.updated_by,
        )

    def _invalidate_caches(self, user_id: str | None = None) -> None:
        """Invalidate relevant caches."""
        if not self.cache_client:
            return
        try:
            self.cache_client.invalidate_tenant_list_cache()
            if user_id:
                self.cache_client.clear_cache_for_user(user_id)
        except Exception as e:
            logger.warning(f"Failed to invalidate cache: {e}")
