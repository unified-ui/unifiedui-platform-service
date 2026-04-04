"""Business logic handlers for workflow operations."""

from __future__ import annotations

import secrets
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import selectinload

from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum, WorkflowTypeEnum
from unifiedui.core.database.models import RecentVisit, Workflow, WorkflowMember, WorkflowTag
from unifiedui.handlers.cache_utils import ResourceCacheInvalidator
from unifiedui.handlers.permission_resolver import (
    check_is_admin,
    get_principal_ids,
    resolve_my_permission,
    resolve_my_permissions_bulk,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from unifiedui.caching.client import CacheClient
    from unifiedui.core.database.client import SQLAlchemyClient
    from unifiedui.core.identity.users import ContextIdentityUser
    from unifiedui.core.vault.client import BaseVaultClient
    from unifiedui.handlers.resource_permissions import ResourcePermissionsHandler
    from unifiedui.handlers.resource_tags import ResourceTagsHandler
    from unifiedui.schema.requests.permissions import SetResourcePermissionRequest
    from unifiedui.schema.requests.workflows import CreateWorkflowRequest, UpdateWorkflowRequest
    from unifiedui.services.agent_service_client import AgentServiceClient

from datetime import UTC

from unifiedui.exc.workflows import (
    WorkflowApiKeysNotAllowedError,
    WorkflowConfigValidationError,
    WorkflowKeyNotFoundError,
    WorkflowNotFoundError,
    WorkflowPermissionNotFoundError,
)
from unifiedui.handlers.validators.workflow_config import WorkflowConfigValidatorFactory
from unifiedui.logger import get_logger
from unifiedui.schema.responses.common import QuickListItemResponse
from unifiedui.schema.responses.principals import PrincipalWithRolesResponse, ResourcePrincipalsResponse
from unifiedui.schema.responses.tags import TagSummary
from unifiedui.schema.responses.workflows import (
    WorkflowKeyResponse,
    WorkflowResponse,
    WorkflowRunDetailResponse,
    WorkflowRunRetryResponse,
    WorkflowRunsListResponse,
)

logger = get_logger(__name__)


class WorkflowHandler:
    """Handler class for workflow business logic."""

    def __init__(
        self,
        db_client: SQLAlchemyClient,
        cache_client: CacheClient | None = None,
        vault_client: BaseVaultClient | None = None,
        permissions_handler: ResourcePermissionsHandler | None = None,
        tags_handler: ResourceTagsHandler | None = None,
        agent_service_client: AgentServiceClient | None = None,
    ):
        """
        Initialize the workflow handler.

        Args:
            db_client: SQLAlchemy database client instance
            cache_client: Optional cache client for Redis caching
            vault_client: Optional vault client for secret management
            permissions_handler: Optional central permissions handler
            tags_handler: Optional central tags handler
            agent_service_client: Optional agent service client for cascade delete
        """
        self.db_client = db_client
        self.cache_client = cache_client
        self.vault_client = vault_client
        self._permissions_handler = permissions_handler
        self._tags_handler = tags_handler
        self._agent_service_client = agent_service_client
        self._cache = ResourceCacheInvalidator(cache_client, "workflows", "workflow")

    @property
    def permissions_handler(self) -> ResourcePermissionsHandler:
        """Get the permissions handler, creating one if needed."""
        if self._permissions_handler is None:
            from unifiedui.handlers.resource_permissions import ResourcePermissionsHandler

            self._permissions_handler = ResourcePermissionsHandler(self.db_client, self.cache_client)
        return self._permissions_handler

    @property
    def tags_handler(self) -> ResourceTagsHandler:
        """Get the tags handler, creating one if needed."""
        if self._tags_handler is None:
            from unifiedui.handlers.resource_tags import ResourceTagsHandler

            self._tags_handler = ResourceTagsHandler(self.db_client, self.cache_client)
        return self._tags_handler

    def list_workflows(
        self,
        tenant_id: str,
        user: ContextIdentityUser,
        skip: int = 0,
        limit: int = 100,
        name_filter: str | None = None,
        is_active: int | None = None,
        tag_ids: list[int] | None = None,
        order_by: str | None = None,
        order_direction: str | None = None,
        view: str | None = None,
        use_cache: bool = True,
        id_list: list[str] | None = None,
    ) -> list[WorkflowResponse] | list[QuickListItemResponse]:
        """
        Get a list of workflows for a tenant (filtered by permissions).

        Args:
            tenant_id: The ID of the tenant
            user: ContextIdentityUser object for permission checking (required)
            skip: Number of items to skip
            limit: Maximum number of items to return
            name_filter: Optional filter by workflow name
            is_active: Optional filter by active status (None=all, 1=active, 0=inactive)
            tag_ids: Optional list of tag IDs to filter by (agents must have AT LEAST ONE of the tags - OR logic)
            order_by: Optional column name to order by
            order_direction: Optional sort direction ('asc' or 'desc')
            use_cache: Whether to use caching

        Returns:
            List of workflow responses
        """
        from unifiedui.core.database.enums import TenantRolesEnum

        logger.info("Listing workflows", extra={"tenant_id": tenant_id, "skip": skip, "limit": limit})

        # Check if user is admin (has TENANT_GLOBAL_ADMIN or WORKFLOWS_ADMIN)
        user_id = user.identity.get_id()
        user_tenants = user.tenants
        matching_tenant = next((t for t in user_tenants if t["tenant"]["id"] == tenant_id), None)

        is_admin = False
        if matching_tenant:
            user_roles = matching_tenant["roles"]
            is_admin = any(
                p in user_roles
                for p in [TenantRolesEnum.TENANT_GLOBAL_ADMIN.value, TenantRolesEnum.WORKFLOWS_ADMIN.value]
            )

        # Only get group IDs if not admin
        identity_group_ids = None
        custom_group_ids = None
        if not is_admin:
            # groups now contains both IDENTITY_GROUP and CUSTOM_GROUP with principal_type attribute
            identity_group_ids = [
                g.id for g in user.groups if g.principal_type == PrincipalTypeEnum.IDENTITY_GROUP.value
            ]
            custom_group_ids = [g.id for g in user.groups if g.principal_type == PrincipalTypeEnum.CUSTOM_GROUP.value]

        # Build cache key with order and is_active parameters
        view_key = view or "full"
        order_key = f"{order_by or 'default'}:{order_direction or 'asc'}"
        is_active_key = "all" if is_active is None else str(is_active)
        cache_key = f"workflows:list:tenant:{tenant_id}:user:{user_id}:skip:{skip}:limit:{limit}:view:{view_key}:order:{order_key}:active:{is_active_key}"

        # Check if any filters are applied (name_filter and tag_ids disable caching)
        has_filters = name_filter is not None or tag_ids is not None or id_list is not None

        # Check cache (disable caching when any filters are applied)
        if use_cache and self.cache_client and not has_filters:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug("Returning cached workflows for tenant %s, user %s", tenant_id, user_id)
                    if view == "quick-list":
                        return [QuickListItemResponse(**item) for item in cached_data]
                    return [WorkflowResponse(**item) for item in cached_data]
            except Exception as e:
                logger.warning("Failed to get cached workflows: %s", e)

        with self.db_client.get_session() as session:
            # If user is admin, return all workflows
            if is_admin:
                query = (
                    select(Workflow)
                    .options(selectinload(Workflow.tags).selectinload(WorkflowTag.tag))
                    .where(Workflow.tenant_id == tenant_id)
                )
                if id_list:
                    query = query.where(Workflow.id.in_(id_list))
                if name_filter:
                    query = query.where(Workflow.name.ilike(f"%{name_filter}%"))
                # Filter by is_active status
                if is_active is not None:
                    query = query.where(Workflow.is_active == bool(is_active))
                # Filter by tags (agents must have ALL specified tags)
                if tag_ids:
                    for tag_id in tag_ids:
                        tag_subquery = select(WorkflowTag.workflow_id).where(
                            WorkflowTag.tenant_id == tenant_id, WorkflowTag.tag_id == tag_id
                        )
                        query = query.where(Workflow.id.in_(tag_subquery))
                # Apply ordering if specified
                if order_by and hasattr(Workflow, order_by):
                    column = getattr(Workflow, order_by)
                    query = query.order_by(column.desc()) if order_direction == "desc" else query.order_by(column.asc())
                query = query.offset(skip).limit(limit)
                workflows = session.execute(query).scalars().all()
            else:
                # Filter by permissions: user must have at least READ permission
                query = (
                    select(Workflow)
                    .options(selectinload(Workflow.tags).selectinload(WorkflowTag.tag))
                    .join(WorkflowMember, Workflow.id == WorkflowMember.workflow_id)
                    .where(Workflow.tenant_id == tenant_id)
                )

                # Add permission filters
                permission_filters = []

                # User permission
                permission_filters.append(WorkflowMember.principal_id == user_id)

                # Identity group permissions
                if identity_group_ids:
                    permission_filters.append(WorkflowMember.principal_id.in_(identity_group_ids))

                # Custom group permissions
                if custom_group_ids:
                    permission_filters.append(WorkflowMember.principal_id.in_(custom_group_ids))

                query = query.where(or_(*permission_filters))

                if id_list:
                    query = query.where(Workflow.id.in_(id_list))

                if name_filter:
                    query = query.where(Workflow.name.ilike(f"%{name_filter}%"))

                # Filter by is_active status
                if is_active is not None:
                    query = query.where(Workflow.is_active == bool(is_active))

                # Filter by tags (agents must have AT LEAST ONE of the specified tags - OR logic)
                if tag_ids:
                    tag_subquery = (
                        select(WorkflowTag.workflow_id)
                        .where(WorkflowTag.tenant_id == tenant_id, WorkflowTag.tag_id.in_(tag_ids))
                        .distinct()
                    )
                    query = query.where(Workflow.id.in_(tag_subquery))

                # Apply ordering if specified
                if order_by and hasattr(Workflow, order_by):
                    column = getattr(Workflow, order_by)
                    query = query.order_by(column.desc()) if order_direction == "desc" else query.order_by(column.asc())

                query = query.distinct().offset(skip).limit(limit)
                workflows = session.execute(query).scalars().all()

            # Return quick-list format if requested
            if view == "quick-list":
                return [QuickListItemResponse(id=agent.id, name=agent.name) for agent in workflows]

            # Convert to response models
            responses = [self._model_to_response(agent) for agent in workflows]

            if is_admin:
                for r in responses:
                    r.my_permission = PermissionActionEnum.ADMIN.value
            else:
                resource_ids = [r.id for r in responses]
                if resource_ids:
                    principal_ids = [user_id]
                    if identity_group_ids:
                        principal_ids.extend(identity_group_ids)
                    if custom_group_ids:
                        principal_ids.extend(custom_group_ids)
                    permissions = resolve_my_permissions_bulk(
                        session, WorkflowMember, "workflow_id", tenant_id, resource_ids, principal_ids
                    )
                    for r in responses:
                        r.my_permission = permissions.get(r.id)

            # Cache the results (only when no filters are applied)
            if use_cache and self.cache_client and not has_filters:
                try:
                    cache_data = [r.model_dump() for r in responses]
                    self.cache_client.client.set(cache_key, cache_data, ttl=300)
                    logger.debug("Cached workflows list for tenant %s, user %s", tenant_id, user_id)
                except Exception as e:
                    logger.warning("Failed to cache workflows: %s", e)

            return responses

    def get_workflow(
        self, tenant_id: str, workflow_id: str, user: ContextIdentityUser | None = None, use_cache: bool = True
    ) -> WorkflowResponse:
        """
        Get a specific workflow by ID.

        Args:
            tenant_id: The ID of the tenant
            workflow_id: The ID of the workflow
            user: Optional user context for permission resolution
            use_cache: Whether to use caching

        Returns:
            Workflow response

        Raises:
            WorkflowNotFoundError: If workflow not found
        """
        logger.info("Fetching workflow", extra={"tenant_id": tenant_id, "workflow_id": workflow_id})

        # Build cache key
        cache_key = f"workflows:detail:tenant:{tenant_id}:workflow:{workflow_id}"

        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug("Returning cached workflow %s", workflow_id)
                    result = WorkflowResponse(**cached_data)
                    if user:
                        with self.db_client.get_session() as session:
                            result.my_permission = self._resolve_user_permission(session, tenant_id, workflow_id, user)
                    return result
            except Exception as e:
                logger.warning("Failed to get cached workflow: %s", e)

        with self.db_client.get_session() as session:
            query = (
                select(Workflow)
                .options(selectinload(Workflow.tags).selectinload(WorkflowTag.tag))
                .where(Workflow.id == workflow_id, Workflow.tenant_id == tenant_id)
            )
            workflow = session.execute(query).scalar_one_or_none()

            if not workflow:
                raise WorkflowNotFoundError(workflow_id)

            result = self._model_to_response(workflow)

            # Cache the result
            if use_cache and self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, result.model_dump(), ttl=300)
                    logger.debug("Cached workflow %s", workflow_id)
                except Exception as e:
                    logger.warning("Failed to cache workflow: %s", e)

            if user:
                result.my_permission = self._resolve_user_permission(session, tenant_id, workflow_id, user)

            return result

    def get_workflow_model(self, tenant_id: str, workflow_id: str) -> Workflow:
        """
        Get the raw workflow DB model by ID.

        Args:
            tenant_id: The ID of the tenant
            workflow_id: The ID of the workflow

        Returns:
            Workflow SQLAlchemy model (detached from session)

        Raises:
            WorkflowNotFoundError: If workflow not found
        """
        with self.db_client.get_session() as session:
            query = select(Workflow).where(Workflow.id == workflow_id, Workflow.tenant_id == tenant_id)
            workflow = session.execute(query).scalar_one_or_none()

            if not workflow:
                raise WorkflowNotFoundError(workflow_id)

            session.expunge(workflow)
            return workflow

    def create_workflow(
        self, tenant_id: str, request: CreateWorkflowRequest, user_id: str, user: ContextIdentityUser
    ) -> WorkflowResponse:
        """
        Create a new workflow.

        Args:
            tenant_id: The ID of the tenant
            request: Workflow creation data
            user_id: ID of the user creating the workflow
            user: The authenticated user context (for IDP access)

        Returns:
            Created workflow response

        Raises:
            WorkflowConfigValidationError: If config validation fails
            UnsupportedWorkflowTypeError: If agent type is not supported
        """
        logger.info(
            "Creating workflow",
            extra={
                "tenant_id": tenant_id,
                "agent_name": request.name,
                "agent_type": request.type.value,
                "user_id": user_id,
            },
        )

        # Validate config based on agent type
        validated_config = WorkflowConfigValidatorFactory.validate_config(
            agent_type=request.type, config=request.config
        )

        workflow_id = str(uuid.uuid4())

        # Generate API keys and store them in vault
        primary_key = self._generate_api_key()
        secondary_key = self._generate_api_key()

        primary_key_vault_uri = None
        secondary_key_vault_uri = None

        if self.vault_client:
            try:
                primary_key_vault_uri = self.vault_client.store_secret(
                    key=f"{tenant_id}/workflows/{workflow_id}/primary-key",
                    value=primary_key,
                    metadata={
                        "tenant_id": tenant_id,
                        "workflow_id": workflow_id,
                        "key_type": "primary",
                    },
                )
                secondary_key_vault_uri = self.vault_client.store_secret(
                    key=f"{tenant_id}/workflows/{workflow_id}/secondary-key",
                    value=secondary_key,
                    metadata={
                        "tenant_id": tenant_id,
                        "workflow_id": workflow_id,
                        "key_type": "secondary",
                    },
                )
                logger.info("Stored API keys in vault for workflow %s", workflow_id)
            except Exception as e:
                logger.error("Failed to store API keys in vault: %s", e)
                raise
        else:
            logger.warning("No vault client configured - API keys will not be stored")

        with self.db_client.get_session() as session:
            # Create workflow
            workflow = Workflow(
                id=workflow_id,
                tenant_id=tenant_id,
                name=request.name,
                description=request.description,
                type=request.type.value,
                config=validated_config,
                is_active=request.is_active,
                allow_api_keys=request.allow_api_keys,
                primary_key_vault_uri=primary_key_vault_uri,
                secondary_key_vault_uri=secondary_key_vault_uri,
                created_by=user_id,
                updated_by=user_id,
            )
            session.add(workflow)

            # Add creator as ADMIN using the central permissions handler
            self.permissions_handler.add_creator_permission(
                session=session,
                resource_type="workflow",
                tenant_id=tenant_id,
                resource_id=workflow_id,
                user_id=user_id,
                user=user,
            )

            session.commit()
            session.refresh(workflow)

            response = self._model_to_response(workflow)

        # Invalidate list cache
        self._invalidate_list_cache(tenant_id)

        logger.info("Created workflow %s", workflow_id)
        return response

    def update_workflow(
        self, tenant_id: str, workflow_id: str, request: UpdateWorkflowRequest, user_id: str
    ) -> WorkflowResponse:
        """
        Update an existing workflow.

        Note: type, primary_key_vault_uri, secondary_key_vault_uri, last_full_import
        are NOT updatable via this method.

        Args:
            tenant_id: The ID of the tenant
            workflow_id: The ID of the workflow
            request: Workflow update data
            user_id: ID of the user updating the workflow

        Returns:
            Updated workflow response

        Raises:
            WorkflowNotFoundError: If workflow not found
            WorkflowConfigValidationError: If config validation fails
        """
        logger.info(
            "Updating workflow",
            extra={"tenant_id": tenant_id, "workflow_id": workflow_id, "user_id": user_id},
        )

        with self.db_client.get_session() as session:
            query = (
                select(Workflow)
                .options(selectinload(Workflow.tags).selectinload(WorkflowTag.tag))
                .where(Workflow.id == workflow_id, Workflow.tenant_id == tenant_id)
            )
            workflow = session.execute(query).scalar_one_or_none()

            if not workflow:
                raise WorkflowNotFoundError(workflow_id)

            # Update fields if provided
            if request.name is not None:
                workflow.name = request.name
            if request.description is not None:
                workflow.description = request.description
            if request.config is not None:
                # Validate config based on the existing agent type
                validated_config = WorkflowConfigValidatorFactory.validate_config(
                    agent_type=WorkflowTypeEnum(workflow.type), config=request.config
                )
                workflow.config = validated_config
            if request.is_active is not None:
                workflow.is_active = request.is_active
            if request.allow_api_keys is not None:
                workflow.allow_api_keys = request.allow_api_keys

            workflow.updated_by = user_id

            session.commit()

            # Re-fetch with tags to ensure they are loaded
            query = (
                select(Workflow)
                .options(selectinload(Workflow.tags).selectinload(WorkflowTag.tag))
                .where(Workflow.id == workflow_id, Workflow.tenant_id == tenant_id)
            )
            workflow = session.execute(query).scalar_one_or_none()
            assert workflow is not None

            response = self._model_to_response(workflow)

            # Invalidate caches
            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, workflow_id)

            logger.info("Updated workflow %s", workflow_id)
            return response

    def delete_workflow(self, tenant_id: str, workflow_id: str) -> None:
        """
        Delete a workflow and cascade delete associated data.

        Args:
            tenant_id: The ID of the tenant
            workflow_id: The ID of the workflow

        Raises:
            WorkflowNotFoundError: If workflow not found
        """
        logger.info("Deleting workflow", extra={"tenant_id": tenant_id, "workflow_id": workflow_id})

        with self.db_client.get_session() as session:
            query = select(Workflow).where(Workflow.id == workflow_id, Workflow.tenant_id == tenant_id)
            workflow = session.execute(query).scalar_one_or_none()

            if not workflow:
                raise WorkflowNotFoundError(workflow_id)

            self._cascade_delete_workflow_data(tenant_id, workflow_id, workflow)

            session.delete(workflow)

            # Clean up recent visits for this resource
            session.execute(
                delete(RecentVisit).where(
                    RecentVisit.tenant_id == tenant_id,
                    RecentVisit.resource_type == "workflow",
                    RecentVisit.resource_id == workflow_id,
                )
            )

            session.commit()

            # Invalidate caches
            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, workflow_id)
            self._invalidate_permissions_cache(tenant_id, workflow_id)

            logger.info("Deleted workflow %s", workflow_id)

    def _cascade_delete_workflow_data(self, tenant_id: str, workflow_id: str, workflow: Workflow) -> None:
        """
        Cascade delete agent service data and vault secrets (best-effort).

        Args:
            tenant_id: Tenant ID
            workflow_id: Workflow ID
            workflow: Workflow model instance
        """
        if self._agent_service_client:
            self._agent_service_client.delete_workflow_data(tenant_id, workflow_id)

        if self.vault_client:
            for vault_uri_attr in ("primary_key_vault_uri", "secondary_key_vault_uri"):
                vault_uri = getattr(workflow, vault_uri_attr, None)
                if vault_uri:
                    try:
                        self.vault_client.delete_secret(vault_uri)
                    except Exception:
                        logger.warning(
                            f"Failed to delete vault secret {vault_uri_attr}",
                            extra={"workflow_id": workflow_id},
                        )

    def duplicate_workflow(
        self, tenant_id: str, workflow_id: str, user_id: str, user: ContextIdentityUser
    ) -> WorkflowResponse:
        """
        Duplicate an existing workflow.

        Creates an exact copy with name + " Copy" (or " Copy(n)" if exists).
        New API keys are generated for the duplicate. Tags are NOT copied.

        Args:
            tenant_id: The ID of the tenant
            workflow_id: The ID of the workflow to duplicate
            user_id: The ID of the user performing the duplication
            user: The authenticated user context

        Returns:
            The newly created workflow response

        Raises:
            WorkflowNotFoundError: If source agent not found
        """
        logger.info("Duplicating workflow", extra={"tenant_id": tenant_id, "workflow_id": workflow_id})

        with self.db_client.get_session() as session:
            query = select(Workflow).where(Workflow.id == workflow_id, Workflow.tenant_id == tenant_id)
            source_agent = session.execute(query).scalar_one_or_none()
            if not source_agent:
                raise WorkflowNotFoundError(workflow_id)

            new_name = self._generate_copy_name(session, tenant_id, source_agent.name)
            new_agent_id = str(uuid.uuid4())

            primary_key = self._generate_api_key()
            secondary_key = self._generate_api_key()
            primary_key_vault_uri = None
            secondary_key_vault_uri = None

            if self.vault_client:
                try:
                    primary_key_vault_uri = self.vault_client.store_secret(
                        key=f"{tenant_id}/workflows/{new_agent_id}/primary-key",
                        value=primary_key,
                        metadata={
                            "tenant_id": tenant_id,
                            "workflow_id": new_agent_id,
                            "key_type": "primary",
                        },
                    )
                    secondary_key_vault_uri = self.vault_client.store_secret(
                        key=f"{tenant_id}/workflows/{new_agent_id}/secondary-key",
                        value=secondary_key,
                        metadata={
                            "tenant_id": tenant_id,
                            "workflow_id": new_agent_id,
                            "key_type": "secondary",
                        },
                    )
                except Exception as e:
                    logger.error("Failed to store API keys in vault for duplicated agent: %s", e)
                    raise

            new_agent = Workflow(
                id=new_agent_id,
                tenant_id=tenant_id,
                name=new_name,
                description=source_agent.description,
                type=source_agent.type,
                config=source_agent.config.copy() if source_agent.config else {},
                is_active=source_agent.is_active,
                allow_api_keys=source_agent.allow_api_keys,
                primary_key_vault_uri=primary_key_vault_uri,
                secondary_key_vault_uri=secondary_key_vault_uri,
                created_by=user_id,
                updated_by=user_id,
            )
            session.add(new_agent)

            self.permissions_handler.add_creator_permission(
                session=session,
                resource_type="workflow",
                tenant_id=tenant_id,
                resource_id=new_agent_id,
                user_id=user_id,
                user=user,
            )

            session.commit()
            session.refresh(new_agent)

            logger.info(
                "Workflow duplicated",
                extra={"source_id": workflow_id, "new_id": new_agent_id, "new_name": new_name},
            )
            self._invalidate_list_cache(tenant_id)
            return self._model_to_response(new_agent)

    def _generate_copy_name(self, session: Session, tenant_id: str, original_name: str) -> str:
        """
        Generate a unique copy name for duplicated resources.

        Args:
            session: SQLAlchemy session
            tenant_id: The tenant ID
            original_name: The original resource name

        Returns:
            A unique name like "Original Copy" or "Original Copy(2)"
        """
        from sqlalchemy import func

        base_name = f"{original_name} Copy"
        query = (
            select(func.count())
            .select_from(Workflow)
            .where(Workflow.tenant_id == tenant_id, Workflow.name.like(f"{original_name} Copy%"))
        )
        count = session.execute(query).scalar() or 0

        if count == 0:
            return base_name
        return f"{base_name}({count + 1})"

    def _invalidate_list_cache(self, tenant_id: str) -> None:
        """Invalidate all list caches for a tenant."""
        self._cache.invalidate_list(tenant_id)

    def _invalidate_detail_cache(self, tenant_id: str, workflow_id: str) -> None:
        """Invalidate detail cache for a specific workflow."""
        self._cache.invalidate_detail(tenant_id, workflow_id)

    def _invalidate_permissions_cache(self, tenant_id: str, workflow_id: str) -> None:
        """Invalidate permissions cache for a specific workflow."""
        self._cache.invalidate_permissions(tenant_id, workflow_id)

    @staticmethod
    def _generate_api_key() -> str:
        """Generate a secure random API key."""
        return secrets.token_urlsafe(32)

    # ========== Config Endpoint Method ==========

    def get_workflow_config(self, tenant_id: str, workflow_id: str, workflow: Workflow, credential_handler):
        """
        Get the full workflow configuration including credential secrets.
        This endpoint is for external systems (like N8N) to fetch complete configuration.

        Args:
            tenant_id: The ID of the tenant
            workflow_id: The ID of the workflow
            workflow: The workflow model (already fetched by middleware)
            credential_handler: Credential handler for fetching secrets

        Returns:
            WorkflowConfigResponse with full config including secrets

        Raises:
            WorkflowNotFoundError: If workflow not found
            InvalidCredentialError: If a credential cannot be fetched
        """
        from unifiedui.exc.chat_agent_config import InvalidCredentialError
        from unifiedui.schema.responses.workflows import (
            CredentialSecretResponse,
            N8NWorkflowConfigSettingsResponse,
            WorkflowConfigResponse,
        )

        logger.info(
            "Fetching workflow config",
            extra={"tenant_id": tenant_id, "workflow_id": workflow_id},
        )

        agent_type = WorkflowTypeEnum(workflow.type)
        config = workflow.config or {}

        # Build settings based on agent type
        if agent_type == WorkflowTypeEnum.N8N:
            # Extract config values
            api_version = config.get("api_version", "v1")
            workflow_endpoint = config.get("workflow_endpoint", "")
            api_credential_id = config.get("api_api_key_credential_id")

            if not api_credential_id:
                raise InvalidCredentialError(
                    credential_id="unknown",
                    message="Workflow config is missing required api_api_key_credential_id",
                )

            # Parse workflow URL to extract host and workflow ID
            n8n_host = ""
            workflow_id = ""
            if workflow_endpoint:
                # Parse URL: http://host:port/workflow/workflowId
                from urllib.parse import urlparse

                parsed = urlparse(workflow_endpoint)
                n8n_host = f"{parsed.scheme}://{parsed.netloc}"

                # Extract workflow ID from path
                path_parts = parsed.path.split("/workflow/")
                if len(path_parts) > 1:
                    workflow_id = path_parts[1].strip("/")

            # Fetch API credential with secret
            try:
                api_credential = credential_handler.get_credential(tenant_id, api_credential_id)
                api_secret = credential_handler.get_credential_secret(tenant_id, api_credential_id)
            except Exception as e:
                logger.error("Failed to fetch API credential: %s", e)
                raise InvalidCredentialError(
                    credential_id=api_credential_id,
                    message=f"Invalid or inaccessible API credential with ID '{api_credential_id}'",
                )

            if api_secret is None:
                logger.error(
                    f"Credential secret is None for credential '{api_credential_id}' — vault may be unavailable"
                )
                raise InvalidCredentialError(
                    credential_id=api_credential_id,
                    message=f"Could not retrieve secret for credential '{api_credential_id}'. Ensure the vault is running and the secret exists.",
                )

            api_credentials = CredentialSecretResponse(
                id=api_credential.id,
                credentials_uri=api_credential.credential_uri,
                name=api_credential.name,
                description=api_credential.description,
                type=api_credential.type,
                is_active=api_credential.is_active,
                secret=api_secret,
            )

            settings = N8NWorkflowConfigSettingsResponse(
                api_version=api_version,
                n8n_host=n8n_host,
                n8n_workflow_endpoint=workflow_endpoint,
                workflow_id=workflow_id,
                api_credentials=api_credentials,
            )
        else:
            # For unsupported types, return raw config
            settings = config

        return WorkflowConfigResponse(
            docversion="v1",
            type=agent_type,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            settings=settings,
        )

    # ========== Workflow Runs Methods ==========

    def _get_n8n_connection_config(
        self,
        tenant_id: str,
        workflow_id: str,
        credential_handler,
    ) -> tuple[str, str, str, str]:
        """Extract n8n connection details from workflow config.

        Args:
            tenant_id: The ID of the tenant
            workflow_id: The ID of the workflow
            credential_handler: Credential handler for fetching API key secrets

        Returns:
            Tuple of (n8n_host, workflow_id, api_version, api_secret)

        Raises:
            WorkflowNotFoundError: If workflow not found
            UnsupportedWorkflowTypeError: If agent type doesn't support workflow runs
            WorkflowConfigValidationError: If required config is missing
        """
        from urllib.parse import urlparse

        from unifiedui.exc.workflows import UnsupportedWorkflowTypeError

        with self.db_client.get_session() as session:
            agent = session.execute(
                select(Workflow).where(
                    Workflow.id == workflow_id,
                    Workflow.tenant_id == tenant_id,
                )
            ).scalar_one_or_none()

            if not agent:
                raise WorkflowNotFoundError(workflow_id)

            agent_type = WorkflowTypeEnum(agent.type)
            if agent_type != WorkflowTypeEnum.N8N:
                raise UnsupportedWorkflowTypeError(agent.type)

            config = agent.config or {}
            workflow_endpoint = config.get("workflow_endpoint", "")
            api_version = config.get("api_version", "v1")
            api_credential_id = config.get("api_api_key_credential_id")

            if not workflow_endpoint or not api_credential_id:
                raise WorkflowConfigValidationError(
                    message="Workflow missing required config for workflow runs",
                    errors=["workflow_endpoint and api_api_key_credential_id are required"],
                )

            parsed = urlparse(workflow_endpoint)
            n8n_host = f"{parsed.scheme}://{parsed.netloc}"
            path_parts = parsed.path.split("/workflow/")
            workflow_id = path_parts[1].strip("/") if len(path_parts) > 1 else ""

            if not workflow_id:
                raise WorkflowConfigValidationError(
                    message="Could not extract workflow ID from workflow_endpoint",
                    errors=["workflow_endpoint must contain /workflow/{id}"],
                )

            api_secret = credential_handler.get_credential_secret(tenant_id, api_credential_id)
            if not api_secret:
                raise WorkflowConfigValidationError(
                    message="Failed to retrieve API key for workflow runs",
                    errors=["Ensure the vault is running and the credential secret exists"],
                )

            return n8n_host, workflow_id, api_version, api_secret

    def get_workflow_runs(
        self,
        tenant_id: str,
        workflow_id: str,
        credential_handler,
        limit: int = 20,
        cursor: str | None = None,
        status: str | None = None,
    ) -> WorkflowRunsListResponse:
        """Fetch workflow execution runs from the external workflow platform.

        Args:
            tenant_id: The ID of the tenant
            workflow_id: The ID of the workflow
            credential_handler: Credential handler for fetching API key secrets
            limit: Maximum number of runs to return
            cursor: Pagination cursor for next page
            status: Filter by execution status

        Returns:
            WorkflowRunsListResponse with list of workflow runs

        Raises:
            WorkflowNotFoundError: If workflow not found
            UnsupportedWorkflowTypeError: If agent type doesn't support workflow runs
            WorkflowConfigValidationError: If config is missing or vault unavailable
        """
        import httpx

        from unifiedui.schema.responses.workflows import WorkflowRunResponse, WorkflowRunsListResponse

        n8n_host, workflow_id, api_version, api_secret = self._get_n8n_connection_config(
            tenant_id, workflow_id, credential_handler
        )

        url = f"{n8n_host}/api/{api_version}/executions"
        params: dict[str, str | int] = {
            "workflowId": workflow_id,
            "limit": min(limit, 100),
        }
        if cursor:
            params["cursor"] = cursor
        if status:
            params["status"] = status

        headers = {"X-N8N-API-KEY": api_secret}

        try:
            with httpx.Client(timeout=15) as client:
                response = client.get(url, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as e:
            logger.error("Failed to fetch workflow runs from N8N: %s", e)
            return WorkflowRunsListResponse(runs=[], next_cursor=None)

        raw_runs = data.get("data", [])
        runs = []
        for run in raw_runs:
            runs.append(
                WorkflowRunResponse(
                    id=str(run.get("id", "")),
                    finished=run.get("finished", False),
                    mode=run.get("mode", "unknown"),
                    startedAt=run.get("startedAt"),
                    stoppedAt=run.get("stoppedAt"),
                    status=run.get("status", "unknown"),
                    workflowName=run.get("workflowName"),
                    retryOf=run.get("retryOf"),
                    retrySuccessId=run.get("retrySuccessId"),
                )
            )

        return WorkflowRunsListResponse(
            runs=runs,
            next_cursor=data.get("nextCursor"),
        )

    def get_workflow_run_detail(
        self,
        tenant_id: str,
        workflow_id: str,
        execution_id: str,
        credential_handler,
    ) -> WorkflowRunDetailResponse:
        """Fetch a single workflow execution with full data from the external platform.

        Args:
            tenant_id: The ID of the tenant
            workflow_id: The ID of the workflow
            execution_id: The execution ID to fetch
            credential_handler: Credential handler for fetching API key secrets

        Returns:
            WorkflowRunDetailResponse with full execution data

        Raises:
            WorkflowNotFoundError: If workflow not found
            UnsupportedWorkflowTypeError: If agent type doesn't support workflow runs
            WorkflowConfigValidationError: If config is missing or execution not found
        """
        import httpx

        from unifiedui.schema.responses.workflows import WorkflowRunDetailResponse

        n8n_host, _workflow_id, api_version, api_secret = self._get_n8n_connection_config(
            tenant_id, workflow_id, credential_handler
        )

        url = f"{n8n_host}/api/{api_version}/executions/{execution_id}"
        headers = {"X-N8N-API-KEY": api_secret}

        try:
            with httpx.Client(timeout=15) as client:
                response = client.get(url, params={"includeData": "true"}, headers=headers)
                response.raise_for_status()
                run = response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise WorkflowConfigValidationError(
                    message=f"Execution {execution_id} not found",
                    errors=[str(e)],
                )
            raise
        except httpx.HTTPError as e:
            logger.error("Failed to fetch workflow run detail from N8N: %s", e)
            raise WorkflowConfigValidationError(
                message=f"Failed to fetch execution {execution_id}",
                errors=[str(e)],
            )

        return WorkflowRunDetailResponse(
            id=str(run.get("id", "")),
            finished=run.get("finished", False),
            mode=run.get("mode", "unknown"),
            startedAt=run.get("startedAt"),
            stoppedAt=run.get("stoppedAt"),
            status=run.get("status", "unknown"),
            workflowName=run.get("workflowName"),
            retryOf=run.get("retryOf"),
            retrySuccessId=run.get("retrySuccessId"),
            data=run.get("data"),
            workflowData=run.get("workflowData"),
        )

    def retry_workflow_run(
        self,
        tenant_id: str,
        workflow_id: str,
        execution_id: str,
        credential_handler,
    ) -> WorkflowRunRetryResponse:
        """Retry a failed workflow execution.

        Args:
            tenant_id: The ID of the tenant
            workflow_id: The ID of the workflow
            execution_id: The execution ID to retry
            credential_handler: Credential handler for fetching API key secrets

        Returns:
            WorkflowRunRetryResponse with retry result

        Raises:
            WorkflowNotFoundError: If workflow not found
            UnsupportedWorkflowTypeError: If agent type doesn't support workflow runs
            WorkflowConfigValidationError: If retry fails
        """
        import httpx

        from unifiedui.schema.responses.workflows import WorkflowRunRetryResponse

        n8n_host, _workflow_id, api_version, api_secret = self._get_n8n_connection_config(
            tenant_id, workflow_id, credential_handler
        )

        url = f"{n8n_host}/api/{api_version}/executions/{execution_id}/retry"
        headers = {"X-N8N-API-KEY": api_secret}

        try:
            with httpx.Client(timeout=30) as client:
                response = client.post(url, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as e:
            logger.error("Failed to retry workflow execution: %s", e)
            raise WorkflowConfigValidationError(
                message=f"Failed to retry execution {execution_id}",
                errors=[str(e)],
            )

        if "message" in data:
            return WorkflowRunRetryResponse(message=data["message"])

        retry_data = data.get("data", data)
        return WorkflowRunRetryResponse(
            id=str(retry_data.get("id", "")),
            retried=retry_data.get("retried", True),
        )

    def start_workflow(
        self,
        tenant_id: str,
        workflow_id: str,
        body: dict | None = None,
        files: list[dict] | None = None,
        query_params: dict[str, str] | None = None,
    ) -> dict:
        """
        Trigger a workflow via its configured webhook URL.

        Args:
            tenant_id: The ID of the tenant
            workflow_id: The ID of the workflow
            body: Optional JSON body to send with the webhook request
            files: Optional list of file dicts with name, mimeType, and base64 data
            query_params: Optional query parameters to append to the webhook URL

        Returns:
            Response from the webhook endpoint

        Raises:
            WorkflowNotFoundError: If workflow not found
            UnsupportedWorkflowTypeError: If agent type doesn't support workflows
            WorkflowConfigValidationError: If webhook_url is not configured
        """
        import httpx

        from unifiedui.exc.workflows import UnsupportedWorkflowTypeError

        with self.db_client.get_session() as session:
            agent = session.execute(
                select(Workflow).where(
                    Workflow.id == workflow_id,
                    Workflow.tenant_id == tenant_id,
                )
            ).scalar_one_or_none()

            if not agent:
                raise WorkflowNotFoundError(workflow_id)

            agent_type = WorkflowTypeEnum(agent.type)
            if agent_type != WorkflowTypeEnum.N8N:
                raise UnsupportedWorkflowTypeError(agent.type)

            config = agent.config or {}
            webhook_url = config.get("webhook_url")

            if not webhook_url:
                from unifiedui.exc.workflows import WorkflowConfigValidationError

                raise WorkflowConfigValidationError(
                    message="No webhook_url configured for this workflow",
                    errors=["webhook_url is required to start a workflow"],
                )

            payload = body or {}
            if files:
                payload["files"] = files

            target_url = webhook_url
            if query_params:
                from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

                parsed = urlparse(webhook_url)
                existing_params = parse_qs(parsed.query)
                existing_params.update({k: [v] for k, v in query_params.items()})
                new_query = urlencode({k: v[0] for k, v in existing_params.items()})
                target_url = urlunparse(parsed._replace(query=new_query))

            try:
                with httpx.Client(timeout=30) as client:
                    response = client.post(
                        target_url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    )
                    response.raise_for_status()
                    try:
                        return response.json()
                    except Exception:
                        return {"status": "ok", "statusCode": response.status_code}
            except httpx.HTTPError as e:
                logger.error("Failed to trigger workflow webhook: %s", e)
                from unifiedui.exc.workflows import WorkflowConfigValidationError

                raise WorkflowConfigValidationError(
                    message=f"Failed to trigger workflow: {e!s}",
                    errors=[str(e)],
                )

    # ========== API Key Management Methods ==========

    def get_api_key(self, tenant_id: str, workflow_id: str, key_number: int) -> WorkflowKeyResponse:
        """
        Get an API key for a workflow.

        Args:
            tenant_id: The ID of the tenant
            workflow_id: The ID of the workflow
            key_number: Key number (1 for primary, 2 for secondary)

        Returns:
            The API key response

        Raises:
            WorkflowNotFoundError: If workflow not found
            WorkflowKeyNotFoundError: If key not found or vault not configured
        """
        logger.info(
            "Getting API key",
            extra={"tenant_id": tenant_id, "workflow_id": workflow_id, "key_number": key_number},
        )

        if key_number not in [1, 2]:
            raise WorkflowKeyNotFoundError(workflow_id, key_number)

        if not self.vault_client:
            raise WorkflowKeyNotFoundError(workflow_id, key_number)

        with self.db_client.get_session() as session:
            query = select(Workflow).where(Workflow.id == workflow_id, Workflow.tenant_id == tenant_id)
            workflow = session.execute(query).scalar_one_or_none()

            if not workflow:
                raise WorkflowNotFoundError(workflow_id)

            if not workflow.allow_api_keys:
                raise WorkflowApiKeysNotAllowedError(workflow_id)

            vault_uri = workflow.primary_key_vault_uri if key_number == 1 else workflow.secondary_key_vault_uri

            if not vault_uri:
                raise WorkflowKeyNotFoundError(workflow_id, key_number)

            key = self.vault_client.get_secret(vault_uri, use_cache=False)

            if not key:
                raise WorkflowKeyNotFoundError(workflow_id, key_number)

            return WorkflowKeyResponse(key=key, key_number=key_number)

    def rotate_api_key(self, tenant_id: str, workflow_id: str, key_number: int, user_id: str) -> WorkflowKeyResponse:
        """
        Rotate an API key for a workflow.

        Args:
            tenant_id: The ID of the tenant
            workflow_id: The ID of the workflow
            key_number: Key number (1 for primary, 2 for secondary)
            user_id: ID of the user rotating the key

        Returns:
            The new API key response

        Raises:
            WorkflowNotFoundError: If workflow not found
            WorkflowKeyNotFoundError: If vault not configured
        """
        logger.info(
            "Rotating API key",
            extra={
                "tenant_id": tenant_id,
                "workflow_id": workflow_id,
                "key_number": key_number,
                "user_id": user_id,
            },
        )

        if key_number not in [1, 2]:
            raise WorkflowKeyNotFoundError(workflow_id, key_number)

        if not self.vault_client:
            raise WorkflowKeyNotFoundError(workflow_id, key_number)

        with self.db_client.get_session() as session:
            query = select(Workflow).where(Workflow.id == workflow_id, Workflow.tenant_id == tenant_id)
            workflow = session.execute(query).scalar_one_or_none()

            if not workflow:
                raise WorkflowNotFoundError(workflow_id)

            if not workflow.allow_api_keys:
                raise WorkflowApiKeysNotAllowedError(workflow_id)

            # Generate new key
            new_key = self._generate_api_key()

            # Determine which vault URI to use
            vault_uri = workflow.primary_key_vault_uri if key_number == 1 else workflow.secondary_key_vault_uri

            if vault_uri:
                # Update existing secret
                success = self.vault_client.update_secret(vault_uri, new_key)
                if not success:
                    logger.error(f"Failed to update key {key_number} in vault for workflow {workflow_id}")
                    raise RuntimeError(f"Failed to rotate key {key_number}")
            else:
                # Create new secret (shouldn't happen normally, but handle gracefully)
                key_type = "primary" if key_number == 1 else "secondary"
                vault_uri = self.vault_client.store_secret(
                    key=f"{tenant_id}/workflows/{workflow_id}/{key_type}-key",
                    value=new_key,
                    metadata={"tenant_id": tenant_id, "workflow_id": workflow_id, "key_type": key_type},
                )

                # Update the model with the new vault URI
                if key_number == 1:
                    workflow.primary_key_vault_uri = vault_uri
                else:
                    workflow.secondary_key_vault_uri = vault_uri

            workflow.updated_by = user_id
            session.commit()

            # Invalidate caches
            self._invalidate_detail_cache(tenant_id, workflow_id)

            logger.info("Rotated key %s for workflow %s", key_number, workflow_id)
            return WorkflowKeyResponse(key=new_key, key_number=key_number)

    def update_last_full_import(self, tenant_id: str, workflow_id: str, user_id: str) -> WorkflowResponse:
        """
        Update the last_full_import timestamp for a workflow.
        This is a system-only operation.

        Args:
            tenant_id: The ID of the tenant
            workflow_id: The ID of the workflow
            user_id: ID of the system user performing the update

        Returns:
            Updated workflow response

        Raises:
            WorkflowNotFoundError: If workflow not found
        """
        from datetime import datetime

        logger.info("Updating last_full_import", extra={"tenant_id": tenant_id, "workflow_id": workflow_id})

        with self.db_client.get_session() as session:
            query = (
                select(Workflow)
                .options(selectinload(Workflow.tags).selectinload(WorkflowTag.tag))
                .where(Workflow.id == workflow_id, Workflow.tenant_id == tenant_id)
            )
            workflow = session.execute(query).scalar_one_or_none()

            if not workflow:
                raise WorkflowNotFoundError(workflow_id)

            workflow.last_full_import = datetime.now(UTC)
            workflow.updated_by = user_id

            session.commit()
            session.refresh(workflow)

            response = self._model_to_response(workflow)

            # Invalidate caches
            self._invalidate_detail_cache(tenant_id, workflow_id)

            return response

    # ========== Permission Management Methods ==========

    def list_workflow_permissions(
        self,
        tenant_id: str,
        workflow_id: str,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        roles: list[str] | None = None,
        is_active: bool | None = None,
        order_by: str | None = None,
        order_direction: str | None = None,
        use_cache: bool = True,
    ) -> ResourcePrincipalsResponse:
        """
        Get all permissions for a workflow.

        Args:
            tenant_id: The ID of the tenant
            workflow_id: The ID of the workflow
            skip: Number of principals to skip
            limit: Maximum number of principals to return
            search: Search term for display_name, principal_name, or mail
            roles: Filter by roles (OR logic)
            is_active: Filter by is_active status
            order_by: Column to order by
            order_direction: Sort direction
            use_cache: Whether to use caching

        Returns:
            List of principals with their permissions

        Raises:
            WorkflowNotFoundError: If workflow not found
        """
        logger.info(
            "Listing workflow permissions",
            extra={"tenant_id": tenant_id, "workflow_id": workflow_id},
        )

        try:
            result = self.permissions_handler.list_permissions(
                resource_type="workflow",
                tenant_id=tenant_id,
                resource_id=workflow_id,
                skip=skip,
                limit=limit,
                search=search,
                roles=roles,
                is_active=is_active,
                order_by=order_by,
                order_direction=order_direction,
                use_cache=use_cache,
            )
        except ValueError as e:
            raise WorkflowNotFoundError(workflow_id) from e

        # Convert to response schema
        principals = [
            PrincipalWithRolesResponse(
                principal_id=p["principal_id"],
                principal_type=p["principal_type"],
                roles=p["roles"],
                mail=p.get("mail"),
                display_name=p.get("display_name"),
                principal_name=p.get("principal_name"),
                description=p.get("description"),
                is_active=p.get("is_active", True),
            )
            for p in result["principals"]
        ]

        return ResourcePrincipalsResponse(
            resource_id=workflow_id,
            resource_type="workflow",
            tenant_id=tenant_id,
            principals=principals,
        )

    def get_workflow_permission(
        self, tenant_id: str, workflow_id: str, principal_id: str
    ) -> PrincipalWithRolesResponse:
        """
        Get permissions for a specific principal on a workflow.

        Args:
            tenant_id: The ID of the tenant
            workflow_id: The ID of the workflow
            principal_id: The ID of the principal

        Returns:
            Principal's permissions

        Raises:
            WorkflowNotFoundError: If workflow not found
        """
        logger.info(
            "Getting workflow permission for principal",
            extra={"tenant_id": tenant_id, "workflow_id": workflow_id, "principal_id": principal_id},
        )

        try:
            result = self.permissions_handler.get_permission(
                resource_type="workflow",
                tenant_id=tenant_id,
                resource_id=workflow_id,
                principal_id=principal_id,
            )
        except ValueError as e:
            # If permission not found, return empty response
            if "No permissions found" in str(e):
                return PrincipalWithRolesResponse(principal_id=principal_id, principal_type="", roles=[])
            raise WorkflowNotFoundError(str(e)) from e

        return PrincipalWithRolesResponse(
            principal_id=result["principal_id"],
            principal_type=result["principal_type"],
            roles=result["roles"],
            mail=result.get("mail"),
            display_name=result.get("display_name"),
            principal_name=result.get("principal_name"),
            description=result.get("description"),
        )

    def set_workflow_permission(
        self,
        tenant_id: str,
        workflow_id: str,
        request: SetResourcePermissionRequest,
        user_id: str,
        user: ContextIdentityUser,
    ) -> PrincipalWithRolesResponse:
        """
        Set or update a permission for a principal on a workflow.

        Args:
            tenant_id: The ID of the tenant
            workflow_id: The ID of the workflow
            request: Permission setting data
            user_id: ID of the user setting the permission

        Returns:
            Created or updated permission response

        Raises:
            WorkflowNotFoundError: If workflow not found
        """
        logger.info(
            "Setting workflow permission",
            extra={
                "tenant_id": tenant_id,
                "workflow_id": workflow_id,
                "principal_id": request.principal_id,
                "agent_role": request.role,
                "user_id": user_id,
            },
        )

        try:
            self.permissions_handler.set_permission(
                resource_type="workflow",
                tenant_id=tenant_id,
                resource_id=workflow_id,
                principal_id=request.principal_id,
                principal_type=request.principal_type.value,
                role=request.role,
                user_id=user_id,
                user=user,
            )
        except ValueError as e:
            raise WorkflowNotFoundError(str(e)) from e

        # Fetch and return the enriched principal data
        return self.get_workflow_permission(
            tenant_id=tenant_id, workflow_id=workflow_id, principal_id=request.principal_id
        )

    def delete_workflow_permission(
        self, tenant_id: str, workflow_id: str, principal_id: str, principal_type: str, role: str
    ) -> None:
        """
        Delete a permission for a principal on a workflow.

        Args:
            tenant_id: The ID of the tenant
            workflow_id: The ID of the workflow
            principal_id: The ID of the principal
            principal_type: The type of principal
            role: The role to delete

        Raises:
            WorkflowNotFoundError: If workflow not found
        """
        logger.info(
            "Deleting workflow permission",
            extra={
                "tenant_id": tenant_id,
                "workflow_id": workflow_id,
                "principal_id": principal_id,
                "agent_role": role,
            },
        )

        try:
            self.permissions_handler.delete_permission(
                resource_type="workflow",
                tenant_id=tenant_id,
                resource_id=workflow_id,
                principal_id=principal_id,
                principal_type=principal_type,
                role=role,
            )
        except ValueError as e:
            if "No permissions found" in str(e) or "not found" in str(e).lower():
                raise WorkflowPermissionNotFoundError(principal_id) from e
            raise WorkflowNotFoundError(str(e)) from e

    @staticmethod
    def _group_permissions_by_principal(results) -> list[dict]:
        """Helper to group permissions by principal."""
        principals_dict = {}
        for member, permission in results:
            key = (member.principal_id, member.principal.principal_type)
            if key not in principals_dict:
                principals_dict[key] = {
                    "principal_id": member.principal_id,
                    "principal_type": member.principal.principal_type,
                    "roles": [],
                }
            principals_dict[key]["roles"].append(permission.permission)
        return list(principals_dict.values())

    @staticmethod
    def _model_to_response(agent: Workflow) -> WorkflowResponse:
        """Convert Workflow model to WorkflowResponse."""
        # Extract tags from the agent's tags relationship
        tags = []
        if hasattr(agent, "tags") and agent.tags:
            for agent_tag in agent.tags:
                if agent_tag.tag:
                    tags.append(TagSummary(id=agent_tag.tag.id, name=agent_tag.tag.name))

        return WorkflowResponse(
            id=agent.id,
            tenant_id=agent.tenant_id,
            name=agent.name,
            description=agent.description,
            type=WorkflowTypeEnum(agent.type),
            is_active=agent.is_active,
            allow_api_keys=agent.allow_api_keys,
            config=agent.config,
            last_full_import=agent.last_full_import,
            tags=tags,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
            created_by=agent.created_by,
            updated_by=agent.updated_by,
        )

    def _resolve_user_permission(
        self, session: Session, tenant_id: str, workflow_id: str, user: ContextIdentityUser
    ) -> str | None:
        """Resolve the user's permission level on a specific workflow."""
        from unifiedui.core.database.enums import TenantRolesEnum

        if check_is_admin(user, tenant_id, [TenantRolesEnum.TENANT_GLOBAL_ADMIN, TenantRolesEnum.WORKFLOWS_ADMIN]):
            return PermissionActionEnum.ADMIN.value
        principal_ids = get_principal_ids(user)
        return resolve_my_permission(session, WorkflowMember, "workflow_id", tenant_id, workflow_id, principal_ids)

    @staticmethod
    def _validate_principal_type(principal_type: str) -> bool:
        """Validate that principal_type is valid."""
        return principal_type in [
            PrincipalTypeEnum.IDENTITY_USER.value,
            PrincipalTypeEnum.IDENTITY_GROUP.value,
            PrincipalTypeEnum.CUSTOM_GROUP.value,
        ]
