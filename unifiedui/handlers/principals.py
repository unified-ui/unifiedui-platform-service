"""Handler for principal operations."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import select

from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.core.database.models import Principal
from unifiedui.core.database.enums import PrincipalTypeEnum
from unifiedui.caching.client import CacheClient
from unifiedui.schema.responses.principals import PrincipalResponse
from unifiedui.logger import get_logger

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser

logger = get_logger(__name__)


class PrincipalHandler:
    """Handler for principal operations."""
    
    def __init__(
        self,
        db_client: SQLAlchemyClient,
        cache_client: Optional[CacheClient] = None
    ):
        """
        Initialize the principal handler.
        
        Args:
            db_client: SQLAlchemy database client instance
            cache_client: Optional cache client for Redis caching
        """
        self.db_client = db_client
        self.cache_client = cache_client

    def refresh_principal(
        self,
        tenant_id: str,
        principal_id: str,
        principal_type: str,
        user: ContextIdentityUser
    ) -> PrincipalResponse:
        """
        Refresh a principal from the identity provider.
        
        Fetches the user/group from the identity provider and updates or creates
        the principal record in the database.
        
        Args:
            tenant_id: The tenant ID where the principal should be stored
            principal_id: The ID of the principal to refresh
            principal_type: The type of principal (IDENTITY_USER or IDENTITY_GROUP)
            user: ContextIdentityUser object for identity provider access
            
        Returns:
            PrincipalResponse with the refreshed principal data
            
        Raises:
            ValueError: If principal_type is invalid or CUSTOM_GROUP
        """
        logger.info(
            "Refreshing principal from identity provider",
            extra={
                "tenant_id": tenant_id,
                "principal_id": principal_id,
                "principal_type": principal_type
            }
        )
        
        # Validate principal type
        if principal_type not in [PrincipalTypeEnum.IDENTITY_USER.value, PrincipalTypeEnum.IDENTITY_GROUP.value]:
            raise ValueError(f"Invalid principal type: {principal_type}. Must be IDENTITY_USER or IDENTITY_GROUP.")
        
        # Fetch from identity provider
        if principal_type == PrincipalTypeEnum.IDENTITY_USER.value:
            identity_data = user.idp.get_user_by_id(principal_id)
            display_name = identity_data.display_name
            mail = identity_data.mail
            description = None
            # For users, principal_name is their email/principal_name from identity data
            principal_name = identity_data.principal_name or identity_data.mail or display_name
        else:  # IDENTITY_GROUP
            identity_data = user.idp.get_group_by_id(principal_id)
            display_name = identity_data.display_name
            mail = None
            description = None
            # For groups, principal_name equals display_name
            principal_name = display_name
        
        with self.db_client.get_session() as session:
            # Try to find existing principal
            existing_principal = session.execute(
                select(Principal).where(
                    Principal.tenant_id == tenant_id,
                    Principal.principal_id == principal_id
                )
            ).scalar_one_or_none()
            
            if existing_principal:
                # Update existing principal
                existing_principal.principal_type = principal_type
                existing_principal.mail = mail
                existing_principal.display_name = display_name
                existing_principal.principal_name = principal_name
                # Note: description is not updated from identity provider
                
                logger.info(
                    "Updated existing principal",
                    extra={"tenant_id": tenant_id, "principal_id": principal_id}
                )
                
                session.flush()
                result = self._model_to_response(existing_principal)
            else:
                # Create new principal
                new_principal = Principal(
                    tenant_id=tenant_id,
                    principal_id=principal_id,
                    principal_type=principal_type,
                    mail=mail,
                    display_name=display_name,
                    principal_name=principal_name,
                    description=description
                )
                session.add(new_principal)
                session.flush()
                
                logger.info(
                    "Created new principal",
                    extra={"tenant_id": tenant_id, "principal_id": principal_id}
                )
                
                result = self._model_to_response(new_principal)
            
            # Invalidate related caches
            self._invalidate_principal_caches(tenant_id, principal_id)
            
            return result

    def get_principal(
        self,
        tenant_id: str,
        principal_id: str,
        use_cache: bool = True
    ) -> Optional[PrincipalResponse]:
        """
        Get a principal by tenant and principal ID.
        
        Args:
            tenant_id: The tenant ID
            principal_id: The principal ID
            use_cache: Whether to use caching
            
        Returns:
            PrincipalResponse or None if not found
        """
        cache_key = f"principals:detail:tenant:{tenant_id}:principal:{principal_id}"
        
        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug("Returning cached principal")
                    return PrincipalResponse(**cached_data)
            except Exception as e:
                logger.warning(f"Failed to get cached principal: {e}")
        
        with self.db_client.get_session() as session:
            principal = session.execute(
                select(Principal).where(
                    Principal.tenant_id == tenant_id,
                    Principal.principal_id == principal_id
                )
            ).scalar_one_or_none()
            
            if not principal:
                return None
            
            result = self._model_to_response(principal)
            
            # Cache the result
            if use_cache and self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, result.model_dump(), ttl=300)
                    logger.debug("Cached principal detail")
                except Exception as e:
                    logger.warning(f"Failed to cache principal: {e}")
            
            return result

    def _model_to_response(self, principal: Principal) -> PrincipalResponse:
        """Convert a Principal model to a PrincipalResponse."""
        return PrincipalResponse(
            tenant_id=principal.tenant_id,
            principal_id=principal.principal_id,
            principal_type=principal.principal_type,
            mail=principal.mail,
            display_name=principal.display_name,
            principal_name=principal.principal_name,
            description=principal.description,
            is_active=principal.is_active,
            created_at=principal.created_at,
            updated_at=principal.updated_at
        )

    def update_principal_status(
        self,
        tenant_id: str,
        principal_id: str,
        is_active: bool
    ) -> PrincipalResponse:
        """
        Update the is_active status of a principal.
        
        Args:
            tenant_id: The tenant ID
            principal_id: The principal ID
            is_active: The new status
            
        Returns:
            PrincipalResponse with the updated principal data
            
        Raises:
            ValueError: If principal is not found
        """
        logger.info(
            "Updating principal status",
            extra={
                "tenant_id": tenant_id,
                "principal_id": principal_id,
                "is_active": is_active
            }
        )
        
        with self.db_client.get_session() as session:
            principal = session.execute(
                select(Principal).where(
                    Principal.tenant_id == tenant_id,
                    Principal.principal_id == principal_id
                )
            ).scalar_one_or_none()
            
            if not principal:
                raise ValueError(f"Principal not found: {principal_id}")
            
            principal.is_active = is_active
            session.flush()
            
            result = self._model_to_response(principal)
            
            # Invalidate related caches
            self._invalidate_principal_caches(tenant_id, principal_id)
            
            logger.info(
                "Updated principal status",
                extra={"tenant_id": tenant_id, "principal_id": principal_id, "is_active": is_active}
            )
            
            return result

    def _invalidate_principal_caches(self, tenant_id: str, principal_id: str) -> None:
        """Invalidate caches related to a principal."""
        if not self.cache_client:
            return
        
        try:
            # Invalidate principal detail cache
            cache_key = f"principals:detail:tenant:{tenant_id}:principal:{principal_id}"
            self.cache_client.client.delete(cache_key)
            
            # Invalidate user identity caches
            self.cache_client.client.delete(f"identity:groups:user:{principal_id}")
            self.cache_client.client.delete(f"identity:custom_groups:user:{principal_id}")
            
            logger.debug("Invalidated principal caches", extra={"tenant_id": tenant_id, "principal_id": principal_id})
        except Exception as e:
            logger.warning(f"Failed to invalidate principal caches: {e}")
