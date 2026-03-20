"""Business logic handlers for external app operations."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select

from unifiedui.core.database.models import ExternalApp
from unifiedui.handlers.cache_utils import ResourceCacheInvalidator

if TYPE_CHECKING:
    from unifiedui.caching.client import CacheClient
    from unifiedui.core.database.client import SQLAlchemyClient
    from unifiedui.schema.requests.external_apps import CreateExternalAppRequest, UpdateExternalAppRequest

from unifiedui.exc.external_apps import ExternalAppNotFoundError
from unifiedui.logger import get_logger
from unifiedui.schema.responses.external_apps import ExternalAppResponse

logger = get_logger(__name__)


class ExternalAppHandler:
    """Handler class for external app business logic."""

    def __init__(
        self,
        db_client: SQLAlchemyClient,
        cache_client: CacheClient | None = None,
    ):
        """Initialize the external app handler.

        Args:
            db_client: SQLAlchemy database client instance
            cache_client: Optional cache client for Redis caching
        """
        self.db_client = db_client
        self.cache_client = cache_client
        self._cache = ResourceCacheInvalidator(cache_client, "external_apps", "ea")

    def list_external_apps(
        self,
        tenant_id: str,
        skip: int = 0,
        limit: int = 100,
        name_filter: str | None = None,
        order_by: str | None = None,
        order_direction: str | None = None,
        use_cache: bool = True,
    ) -> list[ExternalAppResponse]:
        """Get a list of external apps for a tenant.

        Args:
            tenant_id: The ID of the tenant
            skip: Number of items to skip
            limit: Maximum number of items to return
            name_filter: Optional filter by app name
            order_by: Optional column name to order by
            order_direction: Optional sort direction ('asc' or 'desc')
            use_cache: Whether to use caching

        Returns:
            List of external app responses
        """
        logger.info("Listing external apps", extra={"tenant_id": tenant_id, "skip": skip, "limit": limit})

        cache_key = f"external_apps:list:tenant:{tenant_id}:skip:{skip}:limit:{limit}"
        has_filters = name_filter is not None

        if use_cache and self.cache_client and not has_filters:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug("Returning cached external app list")
                    return [ExternalAppResponse(**item) for item in cached_data]
            except Exception as e:
                logger.warning("Failed to get cached external app list: %s", e)

        with self.db_client.get_session() as session:
            query = select(ExternalApp).where(ExternalApp.tenant_id == tenant_id)

            if name_filter:
                query = query.where(ExternalApp.name.ilike(f"%{name_filter}%"))

            if order_by and hasattr(ExternalApp, order_by):
                column = getattr(ExternalApp, order_by)
                query = query.order_by(column.desc()) if order_direction == "desc" else query.order_by(column.asc())

            query = query.offset(skip).limit(limit)
            external_apps = session.execute(query).scalars().all()

            logger.info("Retrieved external apps", extra={"count": len(external_apps)})

            result = [ExternalAppResponse.model_validate(app) for app in external_apps]

            if use_cache and self.cache_client and not has_filters:
                try:
                    data = [r.model_dump() for r in result]
                    self.cache_client.client.set(cache_key, data, ttl=300)
                    logger.debug("Cached external app list")
                except Exception as e:
                    logger.warning("Failed to cache external app list: %s", e)

            return result

    def get_external_app(self, tenant_id: str, external_app_id: str, use_cache: bool = True) -> ExternalAppResponse:
        """Get a specific external app by ID.

        Args:
            tenant_id: The ID of the tenant
            external_app_id: The ID of the external app
            use_cache: Whether to use caching

        Returns:
            External app response

        Raises:
            ExternalAppNotFoundError: If external app not found
        """
        logger.info("Fetching external app", extra={"tenant_id": tenant_id, "external_app_id": external_app_id})

        cache_key = f"external_apps:detail:tenant:{tenant_id}:ea:{external_app_id}"

        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug("Returning cached external app")
                    return ExternalAppResponse(**cached_data)
            except Exception as e:
                logger.warning("Failed to get cached external app: %s", e)

        with self.db_client.get_session() as session:
            query = select(ExternalApp).where(ExternalApp.id == external_app_id, ExternalApp.tenant_id == tenant_id)
            external_app = session.execute(query).scalar_one_or_none()

            if not external_app:
                raise ExternalAppNotFoundError(external_app_id)

            result = ExternalAppResponse.model_validate(external_app)

            if use_cache and self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, result.model_dump(), ttl=300)
                    logger.debug("Cached external app detail")
                except Exception as e:
                    logger.warning("Failed to cache external app: %s", e)

            return result

    def create_external_app(
        self, tenant_id: str, request: CreateExternalAppRequest, user_id: str
    ) -> ExternalAppResponse:
        """Create a new external app.

        Args:
            tenant_id: The ID of the tenant
            request: External app creation data
            user_id: The ID of the user creating the app

        Returns:
            Created external app response
        """
        logger.info("Creating external app", extra={"tenant_id": tenant_id, "app_name": request.name})

        external_app_id = str(uuid.uuid4())

        with self.db_client.get_session() as session:
            external_app = ExternalApp(
                id=external_app_id,
                tenant_id=tenant_id,
                name=request.name,
                description=request.description,
                url=request.url,
                image_url=request.image_url,
                created_by=user_id,
                updated_by=user_id,
            )
            session.add(external_app)
            session.commit()
            session.refresh(external_app)

            logger.info("External app created", extra={"external_app_id": external_app_id})

            self._cache.invalidate_list(tenant_id)

            return ExternalAppResponse.model_validate(external_app)

    def update_external_app(
        self, tenant_id: str, external_app_id: str, request: UpdateExternalAppRequest, user_id: str
    ) -> ExternalAppResponse:
        """Update an existing external app.

        Args:
            tenant_id: The ID of the tenant
            external_app_id: The ID of the external app
            request: External app update data
            user_id: The ID of the user updating the app

        Returns:
            Updated external app response

        Raises:
            ExternalAppNotFoundError: If external app not found
        """
        logger.info("Updating external app", extra={"tenant_id": tenant_id, "external_app_id": external_app_id})

        with self.db_client.get_session() as session:
            query = select(ExternalApp).where(ExternalApp.id == external_app_id, ExternalApp.tenant_id == tenant_id)
            external_app = session.execute(query).scalar_one_or_none()

            if not external_app:
                raise ExternalAppNotFoundError(external_app_id)

            if request.name is not None:
                external_app.name = request.name
            if request.description is not None:
                external_app.description = request.description
            if request.url is not None:
                external_app.url = request.url
            if request.image_url is not None:
                external_app.image_url = request.image_url

            external_app.updated_by = user_id

            session.commit()
            session.refresh(external_app)

            logger.info("External app updated", extra={"external_app_id": external_app_id})

            self._cache.invalidate_list(tenant_id)
            self._cache.invalidate_detail(tenant_id, external_app_id)

            return ExternalAppResponse.model_validate(external_app)

    def delete_external_app(self, tenant_id: str, external_app_id: str) -> None:
        """Delete an external app.

        Args:
            tenant_id: The ID of the tenant
            external_app_id: The ID of the external app

        Raises:
            ExternalAppNotFoundError: If external app not found
        """
        logger.info("Deleting external app", extra={"tenant_id": tenant_id, "external_app_id": external_app_id})

        with self.db_client.get_session() as session:
            query = select(ExternalApp).where(ExternalApp.id == external_app_id, ExternalApp.tenant_id == tenant_id)
            external_app = session.execute(query).scalar_one_or_none()

            if not external_app:
                raise ExternalAppNotFoundError(external_app_id)

            session.delete(external_app)
            session.commit()

            logger.info("External app deleted", extra={"external_app_id": external_app_id})

            self._cache.invalidate_list(tenant_id)
            self._cache.invalidate_detail(tenant_id, external_app_id)
