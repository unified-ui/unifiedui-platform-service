"""Business logic handlers for tenant AI model operations."""

from __future__ import annotations

import contextlib
import json
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select

from unifiedui.core.database.enums import AIModelPurposeGroupEnum
from unifiedui.core.database.models import Credential, TenantAIModel
from unifiedui.exc.tenant_ai_models import (
    InvalidAIModelCredentialError,
    TenantAIModelNotFoundError,
)
from unifiedui.handlers.cache_utils import ResourceCacheInvalidator
from unifiedui.handlers.validators.tenant_ai_model_validator import AIModelConfigValidatorFactory
from unifiedui.logger import get_logger
from unifiedui.schema.responses.tenant_ai_models import AIModelWithSecretResponse, TenantAIModelResponse

if TYPE_CHECKING:
    from collections.abc import Sequence

    from unifiedui.caching.client import CacheClient
    from unifiedui.core.database.client import SQLAlchemyClient
    from unifiedui.core.vault.client import BaseVaultClient
    from unifiedui.schema.requests.tenant_ai_models import CreateTenantAIModelRequest, UpdateTenantAIModelRequest

logger = get_logger(__name__)


class TenantAIModelHandler:
    """Handler class for tenant AI model business logic."""

    def __init__(
        self,
        db_client: SQLAlchemyClient,
        cache_client: CacheClient | None = None,
        vault_client: BaseVaultClient | None = None,
    ):
        """Initialize the tenant AI model handler.

        Args:
            db_client: SQLAlchemy database client instance.
            cache_client: Optional cache client for Redis caching.
            vault_client: Optional vault client for secret retrieval.
        """
        self.db_client = db_client
        self.cache_client = cache_client
        self.vault_client = vault_client
        self._cache = ResourceCacheInvalidator(cache_client, "ai_models", "model")

    def list_tenant_ai_models(
        self,
        tenant_id: str,
        skip: int = 0,
        limit: int = 100,
        name_filter: str | None = None,
        type_filter: Sequence[str] | None = None,
        provider_filter: Sequence[str] | None = None,
        is_active: int | None = None,
        order_by: str | None = None,
        order_direction: str | None = None,
        use_cache: bool = True,
    ) -> list[TenantAIModelResponse]:
        """Get a list of tenant AI models.

        Args:
            tenant_id: The ID of the tenant.
            skip: Number of items to skip.
            limit: Maximum number of items to return.
            name_filter: Optional filter by name.
            type_filter: Optional list of model types to filter by.
            provider_filter: Optional list of providers to filter by.
            is_active: Optional filter by active status.
            order_by: Optional column to order by.
            order_direction: Optional sort direction.
            use_cache: Whether to use caching.

        Returns:
            List of tenant AI model responses.
        """
        logger.info("Listing tenant AI models", extra={"tenant_id": tenant_id})

        order_key = f"{order_by or 'default'}:{order_direction or 'asc'}"
        is_active_key = "all" if is_active is None else str(is_active)
        cache_key = (
            f"ai_models:list:tenant:{tenant_id}:skip:{skip}:limit:{limit}:order:{order_key}:active:{is_active_key}"
        )

        has_filters = name_filter is not None or type_filter is not None or provider_filter is not None

        if use_cache and self.cache_client and not has_filters:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    return [TenantAIModelResponse(**item) for item in cached_data]
            except Exception as e:
                logger.warning("Failed to get cached AI model list: %s", e)

        with self.db_client.get_session() as session:
            query = select(TenantAIModel).where(TenantAIModel.tenant_id == tenant_id)

            if name_filter:
                query = query.where(TenantAIModel.name.ilike(f"%{name_filter}%"))
            if type_filter:
                query = query.where(TenantAIModel.type.in_(type_filter))
            if provider_filter:
                query = query.where(TenantAIModel.provider.in_(provider_filter))
            if is_active is not None:
                query = query.where(TenantAIModel.is_active == bool(is_active))

            if order_by and hasattr(TenantAIModel, order_by):
                column = getattr(TenantAIModel, order_by)
                query = query.order_by(column.desc()) if order_direction == "desc" else query.order_by(column.asc())

            query = query.offset(skip).limit(limit)
            models = session.execute(query).scalars().all()

            result = [self._model_to_response(m) for m in models]

            if use_cache and self.cache_client and not has_filters:
                try:
                    data = [r.model_dump() for r in result]
                    self.cache_client.client.set(cache_key, data, ttl=300)
                except Exception as e:
                    logger.warning("Failed to cache AI model list: %s", e)

            return result

    def get_tenant_ai_model(
        self,
        tenant_id: str,
        model_id: str,
        use_cache: bool = True,
    ) -> TenantAIModelResponse:
        """Get a specific tenant AI model by ID.

        Args:
            tenant_id: The ID of the tenant.
            model_id: The ID of the AI model.
            use_cache: Whether to use caching.

        Returns:
            Tenant AI model response.

        Raises:
            TenantAIModelNotFoundError: If the model is not found.
        """
        cache_key = f"ai_models:detail:tenant:{tenant_id}:model:{model_id}"

        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    return TenantAIModelResponse(**cached_data)
            except Exception as e:
                logger.warning("Failed to get cached AI model: %s", e)

        with self.db_client.get_session() as session:
            model = session.execute(
                select(TenantAIModel).where(
                    TenantAIModel.id == model_id,
                    TenantAIModel.tenant_id == tenant_id,
                )
            ).scalar_one_or_none()

            if not model:
                raise TenantAIModelNotFoundError(model_id)

            result = self._model_to_response(model)

            if use_cache and self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, result.model_dump(), ttl=300)
                except Exception as e:
                    logger.warning("Failed to cache AI model: %s", e)

            return result

    def create_tenant_ai_model(
        self,
        tenant_id: str,
        request: CreateTenantAIModelRequest,
        user_id: str,
    ) -> TenantAIModelResponse:
        """Create a new tenant AI model.

        Args:
            tenant_id: The ID of the tenant.
            request: AI model creation request data.
            user_id: ID of the creating user.

        Returns:
            Created AI model response.

        Raises:
            InvalidAIModelCredentialError: If the credential is invalid.
            TenantAIModelConfigValidationError: If the config is invalid.
        """
        logger.info("Creating tenant AI model", extra={"tenant_id": tenant_id, "model_name": request.name})

        validated_config = AIModelConfigValidatorFactory.validate_config(
            provider=request.provider,
            config=request.config,
        )

        model_id = str(uuid.uuid4())

        with self.db_client.get_session() as session:
            if request.credential_id:
                credential = session.execute(
                    select(Credential).where(
                        Credential.id == request.credential_id,
                        Credential.tenant_id == tenant_id,
                    )
                ).scalar_one_or_none()
                if not credential:
                    raise InvalidAIModelCredentialError(request.credential_id)

            purpose_groups_values = [pg.value for pg in request.purpose_groups]

            ai_model = TenantAIModel(
                id=model_id,
                tenant_id=tenant_id,
                name=request.name,
                description=request.description,
                type=request.type.value,
                provider=request.provider.value,
                purpose_groups=purpose_groups_values,
                config=validated_config,
                credential_id=request.credential_id,
                priority=request.priority,
                is_active=request.is_active,
                created_by=user_id,
                updated_by=user_id,
            )
            session.add(ai_model)
            session.commit()
            session.refresh(ai_model)

            self._invalidate_list_cache(tenant_id)

            return self._model_to_response(ai_model)

    def update_tenant_ai_model(
        self,
        tenant_id: str,
        model_id: str,
        request: UpdateTenantAIModelRequest,
        user_id: str,
    ) -> TenantAIModelResponse:
        """Update an existing tenant AI model.

        Args:
            tenant_id: The ID of the tenant.
            model_id: The ID of the AI model.
            request: AI model update request data.
            user_id: ID of the updating user.

        Returns:
            Updated AI model response.

        Raises:
            TenantAIModelNotFoundError: If the model is not found.
            InvalidAIModelCredentialError: If the credential is invalid.
        """
        logger.info("Updating tenant AI model", extra={"tenant_id": tenant_id, "model_id": model_id})

        with self.db_client.get_session() as session:
            ai_model = session.execute(
                select(TenantAIModel).where(
                    TenantAIModel.id == model_id,
                    TenantAIModel.tenant_id == tenant_id,
                )
            ).scalar_one_or_none()

            if not ai_model:
                raise TenantAIModelNotFoundError(model_id)

            if request.name is not None:
                ai_model.name = request.name
            if request.description is not None:
                ai_model.description = request.description
            if request.purpose_groups is not None:
                ai_model.purpose_groups = [pg.value for pg in request.purpose_groups]
            if request.config is not None:
                from unifiedui.core.database.enums import AIModelProviderEnum

                provider = AIModelProviderEnum(ai_model.provider)
                validated_config = AIModelConfigValidatorFactory.validate_config(
                    provider=provider,
                    config=request.config,
                )
                ai_model.config = validated_config
            if request.credential_id is not None:
                if request.credential_id:
                    credential = session.execute(
                        select(Credential).where(
                            Credential.id == request.credential_id,
                            Credential.tenant_id == tenant_id,
                        )
                    ).scalar_one_or_none()
                    if not credential:
                        raise InvalidAIModelCredentialError(request.credential_id)
                    ai_model.credential_id = request.credential_id
                else:
                    ai_model.credential_id = None
            if request.priority is not None:
                ai_model.priority = request.priority
            if request.is_active is not None:
                ai_model.is_active = request.is_active

            ai_model.updated_by = user_id

            session.commit()
            session.refresh(ai_model)

            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, model_id)

            return self._model_to_response(ai_model)

    def delete_tenant_ai_model(
        self,
        tenant_id: str,
        model_id: str,
    ) -> None:
        """Delete a tenant AI model.

        Args:
            tenant_id: The ID of the tenant.
            model_id: The ID of the AI model.

        Raises:
            TenantAIModelNotFoundError: If the model is not found.
        """
        logger.info("Deleting tenant AI model", extra={"tenant_id": tenant_id, "model_id": model_id})

        with self.db_client.get_session() as session:
            ai_model = session.execute(
                select(TenantAIModel).where(
                    TenantAIModel.id == model_id,
                    TenantAIModel.tenant_id == tenant_id,
                )
            ).scalar_one_or_none()

            if not ai_model:
                raise TenantAIModelNotFoundError(model_id)

            session.delete(ai_model)
            session.commit()

            self._invalidate_list_cache(tenant_id)
            self._invalidate_detail_cache(tenant_id, model_id)

    def get_models_by_purpose(
        self,
        tenant_id: str,
        purpose_group: str,
        model_type: str | None = None,
    ) -> list[AIModelWithSecretResponse]:
        """Get active AI models by purpose group with decrypted credentials (S2S only).

        Args:
            tenant_id: The ID of the tenant.
            purpose_group: The purpose group to filter by.
            model_type: Optional model type filter (LLM_MODEL or EMBEDDING_MODEL).

        Returns:
            List of AI models with decrypted credential secrets.
        """
        logger.info("Getting AI models by purpose", extra={"tenant_id": tenant_id, "purpose_group": purpose_group})

        with self.db_client.get_session() as session:
            query = select(TenantAIModel).where(
                TenantAIModel.tenant_id == tenant_id,
                TenantAIModel.is_active,
            )

            if model_type:
                query = query.where(TenantAIModel.type == model_type)

            query = query.order_by(TenantAIModel.priority.asc())
            models = session.execute(query).scalars().all()

            result = []
            for model in models:
                purpose_groups = model.purpose_groups or []
                if purpose_group not in purpose_groups:
                    continue

                credential_secret = None
                if model.credential_id and self.vault_client:
                    credential = session.execute(
                        select(Credential).where(
                            Credential.id == model.credential_id,
                            Credential.tenant_id == tenant_id,
                        )
                    ).scalar_one_or_none()
                    if credential and credential.credential_uri:
                        try:
                            secret_str = self.vault_client.get_secret(credential.credential_uri, use_cache=False)
                            if secret_str:
                                try:
                                    credential_secret = json.loads(secret_str)
                                except (json.JSONDecodeError, ValueError):
                                    credential_secret = {"api_key": secret_str}
                        except Exception as e:
                            logger.error("Failed to decrypt credential secret: %s", e)

                result.append(
                    AIModelWithSecretResponse(
                        id=model.id,
                        type=model.type,
                        provider=model.provider,
                        config=model.config or {},
                        credential_secret=credential_secret,
                        priority=model.priority,
                    )
                )

            return result

    def _invalidate_list_cache(self, tenant_id: str) -> None:
        """Invalidate cached AI model list for a tenant.

        Args:
            tenant_id: The tenant ID for cache scoping.
        """
        self._cache.invalidate_list(tenant_id)

    def _invalidate_detail_cache(self, tenant_id: str, model_id: str) -> None:
        """Invalidate cached AI model detail.

        Args:
            tenant_id: The tenant ID for cache scoping.
            model_id: The AI model ID.
        """
        self._cache.invalidate_detail(tenant_id, model_id)

    @staticmethod
    def _model_to_response(model: TenantAIModel) -> TenantAIModelResponse:
        """Convert a TenantAIModel ORM model to a response schema.

        Args:
            model: The ORM model instance.

        Returns:
            The response schema.
        """
        purpose_groups = model.purpose_groups or []
        purpose_group_enums = []
        for pg in purpose_groups:
            with contextlib.suppress(ValueError):
                purpose_group_enums.append(AIModelPurposeGroupEnum(pg))

        return TenantAIModelResponse(
            id=model.id,
            tenant_id=model.tenant_id,
            name=model.name,
            description=model.description,
            type=model.type,
            provider=model.provider,
            purpose_groups=purpose_group_enums,
            config=model.config or {},
            credential_id=model.credential_id,
            priority=model.priority,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
            created_by=model.created_by,
            updated_by=model.updated_by,
        )
