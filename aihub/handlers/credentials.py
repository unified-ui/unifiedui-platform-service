"""Business logic handlers for credential operations."""
import uuid
from typing import Optional, List

from sqlalchemy import select, or_

from aihub.core.database.client import SQLAlchemyClient
from aihub.core.database.models import Credential, CredentialPermission
from aihub.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from aihub.core.vault.client import BaseVaultClient
from aihub.caching.client import CacheClient
from aihub.schema.requests.credentials import CreateCredentialRequest, UpdateCredentialRequest
from aihub.schema.requests.credential_permissions import SetCredentialPermissionRequest
from aihub.schema.responses.credentials import CredentialResponse
from aihub.schema.responses.credential_permissions import CredentialPermissionResponse, CredentialPermissionsListResponse
from aihub.exc.credentials import CredentialNotFoundError
from aihub.logger import get_logger

logger = get_logger(__name__)


class CredentialHandler:
    """Handler class for credential business logic."""

    def __init__(
        self,
        db_client: SQLAlchemyClient,
        vault_client: BaseVaultClient,
        cache_client: Optional[CacheClient] = None
    ):
        """
        Initialize the credential handler.
        
        Args:
            db_client: SQLAlchemy database client instance
            vault_client: Vault client for secret management
            cache_client: Optional cache client for Redis caching
        """
        self.db_client = db_client
        self.vault_client = vault_client
        self.cache_client = cache_client

    def list_credentials(
        self,
        tenant_id: str,
        skip: int = 0,
        limit: int = 100,
        name_filter: Optional[str] = None,
        user_id: Optional[str] = None,
        identity_group_ids: Optional[List[str]] = None,
        custom_group_ids: Optional[List[str]] = None,
        is_admin: bool = False,
        use_cache: bool = True
    ) -> List[CredentialResponse]:
        """
        Get a list of credentials for a tenant (filtered by permissions).
        
        Args:
            tenant_id: The ID of the tenant
            skip: Number of items to skip
            limit: Maximum number of items to return
            name_filter: Optional filter by credential name
            user_id: User ID for permission filtering
            identity_group_ids: List of identity group IDs for permission filtering
            custom_group_ids: List of custom group IDs for permission filtering
            is_admin: If True, skip permission filtering (GLOBAL_ADMIN or CREDENTIALS_ADMIN)
            use_cache: Whether to use caching
            
        Returns:
            List of credential responses (without secret values)
        """
        logger.info("Listing credentials", extra={"tenant_id": tenant_id, "skip": skip, "limit": limit})
        
        # Build cache key
        filter_key = name_filter or "all"
        cache_key = f"credentials:list:tenant:{tenant_id}:skip:{skip}:limit:{limit}:filter:{filter_key}"
        
        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Returning cached credential list")
                    return [CredentialResponse(**item) for item in cached_data]
            except Exception as e:
                logger.warning(f"Failed to get cached credential list: {e}")
        
        with self.db_client.get_session() as session:
            query = select(Credential).where(Credential.tenant_id == tenant_id)
            
            # Filter by permissions if not admin
            if not is_admin and user_id:
                # Build permission filter
                principal_ids = [user_id]
                if identity_group_ids:
                    principal_ids.extend(identity_group_ids)
                if custom_group_ids:
                    principal_ids.extend(custom_group_ids)
                
                # Subquery for credentials with permissions
                permission_subquery = (
                    select(CredentialPermission.credential_id)
                    .where(
                        CredentialPermission.tenant_id == tenant_id,
                        CredentialPermission.principal_id.in_(principal_ids)
                    )
                    .distinct()
                )
                
                query = query.where(Credential.id.in_(permission_subquery))
            
            if name_filter:
                query = query.where(Credential.name.ilike(f"%{name_filter}%"))
            
            query = query.offset(skip).limit(limit)
            credentials = session.execute(query).scalars().all()
            
            logger.info("Retrieved credentials", extra={"count": len(credentials)})
            result = [self._model_to_response(cred) for cred in credentials]
            
            # Cache the result
            if self.cache_client:
                try:
                    cache_data = [item.model_dump() for item in result]
                    self.cache_client.client.set(cache_key, cache_data, ttl=300)  # 5 minutes
                    logger.debug(f"Cached credential list (TTL: 300s)")
                except Exception as e:
                    logger.warning(f"Failed to cache credential list: {e}")
            
            return result

    def get_credential(
        self,
        tenant_id: str,
        credential_id: str,
        use_cache: bool = True
    ) -> CredentialResponse:
        """
        Get a specific credential by ID (without secret value).
        
        Args:
            tenant_id: The ID of the tenant
            credential_id: The ID of the credential
            use_cache: Whether to use caching
            
        Returns:
            Credential response (without secret value)
            
        Raises:
            CredentialNotFoundError: If credential not found
        """
        logger.info("Fetching credential", extra={"tenant_id": tenant_id, "credential_id": credential_id})
        
        # Build cache key
        cache_key = f"credentials:detail:tenant:{tenant_id}:cred:{credential_id}"
        
        # Check cache
        if use_cache and self.cache_client:
            try:
                cached_data = self.cache_client.client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Returning cached credential {credential_id}")
                    return CredentialResponse(**cached_data)
            except Exception as e:
                logger.warning(f"Failed to get cached credential: {e}")
        
        with self.db_client.get_session() as session:
            query = select(Credential).where(
                Credential.id == credential_id,
                Credential.tenant_id == tenant_id
            )
            credential = session.execute(query).scalar_one_or_none()
            
            if not credential:
                logger.warning("Credential not found", extra={"credential_id": credential_id})
                raise CredentialNotFoundError(credential_id)
            
            logger.info("Credential retrieved", extra={"credential_id": credential_id})
            result = self._model_to_response(credential)
            
            # Cache the result
            if self.cache_client:
                try:
                    self.cache_client.client.set(cache_key, result.model_dump(), ttl=600)  # 10 minutes
                    logger.debug(f"Cached credential {credential_id} (TTL: 600s)")
                except Exception as e:
                    logger.warning(f"Failed to cache credential: {e}")
            
            return result

    def get_credential_secret(
        self,
        tenant_id: str,
        credential_id: str
    ) -> Optional[str]:
        """
        Get the actual secret value from vault (for internal use only).
        This method should NOT be exposed to end users via API.
        
        Args:
            tenant_id: The ID of the tenant
            credential_id: The ID of the credential
            
        Returns:
            Secret value or None
            
        Raises:
            CredentialNotFoundError: If credential not found
        """
        logger.info("Fetching credential secret", extra={"tenant_id": tenant_id, "credential_id": credential_id})
        
        with self.db_client.get_session() as session:
            query = select(Credential).where(
                Credential.id == credential_id,
                Credential.tenant_id == tenant_id
            )
            credential = session.execute(query).scalar_one_or_none()
            
            if not credential:
                raise CredentialNotFoundError(credential_id)
            
            # Fetch secret from vault (with encrypted caching)
            secret = self.vault_client.get_secret(credential.credential_uri)
            logger.debug(f"Retrieved secret for credential {credential_id}")
            return secret

    def create_credential(
        self,
        tenant_id: str,
        request: CreateCredentialRequest,
        user_id: str
    ) -> CredentialResponse:
        """
        Create a new credential and store secret in vault.
        
        Args:
            tenant_id: The ID of the tenant
            request: Credential creation data
            user_id: ID of the user creating the credential
            
        Returns:
            Created credential response
        """
        logger.info("Creating credential", extra={"tenant_id": tenant_id, "name": request.name, "user_id": user_id})
        
        credential_id = str(uuid.uuid4())
        
        # Store secret in vault first
        try:
            vault_uri = self.vault_client.store_secret(
                key=f"{tenant_id}/{credential_id}",
                value=request.secret_value,
                metadata=request.metadata
            )
            logger.info(f"Stored secret in vault for credential {credential_id}")
        except Exception as e:
            logger.error(f"Failed to store secret in vault: {e}")
            raise
        
        with self.db_client.get_session() as session:
            # Create credential (without secret)
            credential = Credential(
                id=credential_id,
                tenant_id=tenant_id,
                name=request.name,
                description=request.description,
                type=request.credential_type,
                source="vault",  # Source is always vault
                credential_uri=vault_uri,
                created_by=user_id,
                updated_by=user_id
            )
            session.add(credential)
            
            # Invalidate caches
            if self.cache_client:
                try:
                    self._invalidate_list_cache(tenant_id)
                    logger.debug(f"Invalidated credential list cache")
                except Exception as e:
                    logger.warning(f"Failed to invalidate cache: {e}")
            
            logger.info("Credential created", extra={"credential_id": credential_id})
            return self._model_to_response(credential)

    def update_credential(
        self,
        tenant_id: str,
        credential_id: str,
        request: UpdateCredentialRequest,
        user_id: str
    ) -> CredentialResponse:
        """
        Update an existing credential.
        
        Args:
            tenant_id: The ID of the tenant
            credential_id: The ID of the credential
            request: Credential update data
            user_id: ID of the user updating the credential
            
        Returns:
            Updated credential response
            
        Raises:
            CredentialNotFoundError: If credential not found
        """
        logger.info("Updating credential", extra={"tenant_id": tenant_id, "credential_id": credential_id})
        
        with self.db_client.get_session() as session:
            query = select(Credential).where(
                Credential.id == credential_id,
                Credential.tenant_id == tenant_id
            )
            credential = session.execute(query).scalar_one_or_none()
            
            if not credential:
                raise CredentialNotFoundError(credential_id)
            
            # Update secret in vault if provided
            if request.secret_value is not None:
                try:
                    self.vault_client.update_secret(
                        uri=credential.credential_uri,
                        value=request.secret_value,
                        metadata=request.metadata
                    )
                    logger.info(f"Updated secret in vault for credential {credential_id}")
                except Exception as e:
                    logger.error(f"Failed to update secret in vault: {e}")
                    raise
            
            # Update credential metadata
            if request.name is not None:
                credential.name = request.name
            if request.description is not None:
                credential.description = request.description
            if request.credential_type is not None:
                credential.type = request.credential_type
            if request.metadata is not None:
                # Metadata is stored as part of the vault secret, not in DB
                pass
            
            credential.updated_by = user_id
            
            # Invalidate caches
            if self.cache_client:
                try:
                    self._invalidate_list_cache(tenant_id)
                    self._invalidate_detail_cache(tenant_id, credential_id)
                    logger.debug(f"Invalidated caches for credential {credential_id}")
                except Exception as e:
                    logger.warning(f"Failed to invalidate cache: {e}")
            
            logger.info("Credential updated", extra={"credential_id": credential_id})
            return self._model_to_response(credential)

    def delete_credential(
        self,
        tenant_id: str,
        credential_id: str
    ) -> None:
        """
        Delete a credential and its secret from vault.
        
        Args:
            tenant_id: The ID of the tenant
            credential_id: The ID of the credential
            
        Raises:
            CredentialNotFoundError: If credential not found
        """
        logger.info("Deleting credential", extra={"tenant_id": tenant_id, "credential_id": credential_id})
        
        with self.db_client.get_session() as session:
            query = select(Credential).where(
                Credential.id == credential_id,
                Credential.tenant_id == tenant_id
            )
            credential = session.execute(query).scalar_one_or_none()
            
            if not credential:
                raise CredentialNotFoundError(credential_id)
            
            vault_uri = credential.credential_uri
            
            # Delete from database first
            session.delete(credential)
            
            # Delete from vault
            try:
                self.vault_client.delete_secret(vault_uri)
                logger.info(f"Deleted secret from vault for credential {credential_id}")
            except Exception as e:
                logger.warning(f"Failed to delete secret from vault: {e}")
                # Continue even if vault deletion fails
            
            # Invalidate caches
            if self.cache_client:
                try:
                    self._invalidate_list_cache(tenant_id)
                    self._invalidate_detail_cache(tenant_id, credential_id)
                    logger.debug(f"Invalidated caches for credential {credential_id}")
                except Exception as e:
                    logger.warning(f"Failed to invalidate cache: {e}")
            
            logger.info("Credential deleted", extra={"credential_id": credential_id})

    def _invalidate_list_cache(self, tenant_id: str) -> None:
        """Invalidate all list caches for a tenant."""
        if self.cache_client:
            pattern = f"credentials:list:tenant:{tenant_id}:*"
            self.cache_client.client.delete_pattern(pattern)

    def _invalidate_detail_cache(self, tenant_id: str, credential_id: str) -> None:
        """Invalidate detail cache for a specific credential."""
        if self.cache_client:
            cache_key = f"credentials:detail:tenant:{tenant_id}:cred:{credential_id}"
            self.cache_client.client.delete(cache_key)

    # ========== Permission Management Methods ==========

    def list_credential_permissions(
        self,
        tenant_id: str,
        credential_id: str
    ) -> CredentialPermissionsListResponse:
        """
        List all permissions for a credential.
        
        Args:
            tenant_id: The ID of the tenant
            credential_id: The ID of the credential
            
        Returns:
            List of credential permissions
            
        Raises:
            CredentialNotFoundError: If credential not found
        """
        logger.info("Listing credential permissions", extra={"tenant_id": tenant_id, "credential_id": credential_id})
        
        with self.db_client.get_session() as session:
            # Verify credential exists
            cred_query = select(Credential).where(
                Credential.id == credential_id,
                Credential.tenant_id == tenant_id
            )
            credential = session.execute(cred_query).scalar_one_or_none()
            if not credential:
                raise CredentialNotFoundError(credential_id)
            
            # Get permissions
            perm_query = select(CredentialPermission).where(
                CredentialPermission.credential_id == credential_id,
                CredentialPermission.tenant_id == tenant_id
            )
            permissions = session.execute(perm_query).scalars().all()
            
            logger.info("Retrieved credential permissions", extra={"count": len(permissions)})
            return CredentialPermissionsListResponse(
                permissions=[self._permission_to_response(perm) for perm in permissions],
                total=len(permissions)
            )

    def get_credential_permission(
        self,
        tenant_id: str,
        credential_id: str,
        principal_id: str
    ) -> CredentialPermissionResponse:
        """
        Get a specific credential permission.
        
        Args:
            tenant_id: The ID of the tenant
            credential_id: The ID of the credential
            principal_id: The ID of the principal
            
        Returns:
            Credential permission
            
        Raises:
            CredentialNotFoundError: If credential or permission not found
        """
        logger.info("Getting credential permission", extra={
            "tenant_id": tenant_id,
            "credential_id": credential_id,
            "principal_id": principal_id
        })
        
        with self.db_client.get_session() as session:
            # Verify credential exists
            cred_query = select(Credential).where(
                Credential.id == credential_id,
                Credential.tenant_id == tenant_id
            )
            credential = session.execute(cred_query).scalar_one_or_none()
            if not credential:
                raise CredentialNotFoundError(credential_id)
            
            # Get permission
            perm_query = select(CredentialPermission).where(
                CredentialPermission.credential_id == credential_id,
                CredentialPermission.tenant_id == tenant_id,
                CredentialPermission.principal_id == principal_id
            )
            permission = session.execute(perm_query).scalar_one_or_none()
            
            if not permission:
                raise CredentialNotFoundError(f"Permission for principal {principal_id} not found")
            
            return self._permission_to_response(permission)

    def set_credential_permission(
        self,
        tenant_id: str,
        credential_id: str,
        request: SetCredentialPermissionRequest
    ) -> CredentialPermissionResponse:
        """
        Set or update a credential permission.
        
        Args:
            tenant_id: The ID of the tenant
            credential_id: The ID of the credential
            request: Permission data
            
        Returns:
            Created or updated permission
            
        Raises:
            CredentialNotFoundError: If credential not found
        """
        logger.info("Setting credential permission", extra={
            "tenant_id": tenant_id,
            "credential_id": credential_id,
            "principal_id": request.principal_id
        })
        
        with self.db_client.get_session() as session:
            # Verify credential exists
            cred_query = select(Credential).where(
                Credential.id == credential_id,
                Credential.tenant_id == tenant_id
            )
            credential = session.execute(cred_query).scalar_one_or_none()
            if not credential:
                raise CredentialNotFoundError(credential_id)
            
            # Check if permission already exists
            perm_query = select(CredentialPermission).where(
                CredentialPermission.credential_id == credential_id,
                CredentialPermission.tenant_id == tenant_id,
                CredentialPermission.principal_id == request.principal_id
            )
            permission = session.execute(perm_query).scalar_one_or_none()
            
            if permission:
                # Update existing permission
                permission.action = request.permission
                logger.info("Updated credential permission")
            else:
                # Create new permission
                permission = CredentialPermission(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    credential_id=credential_id,
                    principal_id=request.principal_id,
                    action=request.permission,
                    name=f"{request.principal_type.value}_{request.principal_id}",
                    description=f"Permission for {request.principal_type.value}"
                )
                session.add(permission)
                logger.info("Created credential permission")
            
            # Invalidate caches
            if self.cache_client:
                try:
                    self._invalidate_list_cache(tenant_id)
                    logger.debug("Invalidated credential list cache")
                except Exception as e:
                    logger.warning(f"Failed to invalidate cache: {e}")
            
            return self._permission_to_response(permission)

    def delete_credential_permission(
        self,
        tenant_id: str,
        credential_id: str,
        principal_id: str
    ) -> None:
        """
        Delete a credential permission.
        
        Args:
            tenant_id: The ID of the tenant
            credential_id: The ID of the credential
            principal_id: The ID of the principal
            
        Raises:
            CredentialNotFoundError: If credential or permission not found
        """
        logger.info("Deleting credential permission", extra={
            "tenant_id": tenant_id,
            "credential_id": credential_id,
            "principal_id": principal_id
        })
        
        with self.db_client.get_session() as session:
            # Verify credential exists
            cred_query = select(Credential).where(
                Credential.id == credential_id,
                Credential.tenant_id == tenant_id
            )
            credential = session.execute(cred_query).scalar_one_or_none()
            if not credential:
                raise CredentialNotFoundError(credential_id)
            
            # Get and delete permission
            perm_query = select(CredentialPermission).where(
                CredentialPermission.credential_id == credential_id,
                CredentialPermission.tenant_id == tenant_id,
                CredentialPermission.principal_id == principal_id
            )
            permission = session.execute(perm_query).scalar_one_or_none()
            
            if not permission:
                raise CredentialNotFoundError(f"Permission for principal {principal_id} not found")
            
            session.delete(permission)
            
            # Invalidate caches
            if self.cache_client:
                try:
                    self._invalidate_list_cache(tenant_id)
                    logger.debug("Invalidated credential list cache")
                except Exception as e:
                    logger.warning(f"Failed to invalidate cache: {e}")
            
            logger.info("Deleted credential permission")

    @staticmethod
    def _permission_to_response(permission: CredentialPermission) -> CredentialPermissionResponse:
        """Convert CredentialPermission model to response."""
        return CredentialPermissionResponse(
            id=permission.id,
            credential_id=permission.credential_id,
            tenant_id=permission.tenant_id,
            principal_id=permission.principal_id,
            principal_type=PrincipalTypeEnum.IDENTITY_USER,  # Default, should be stored in DB
            action=permission.action,
            created_at=permission.created_at,
            updated_at=permission.updated_at
        )

    @staticmethod
    def _model_to_response(credential: Credential) -> CredentialResponse:
        """Convert Credential model to response."""
        return CredentialResponse(
            id=credential.id,
            tenant_id=credential.tenant_id,
            name=credential.name,
            description=credential.description,
            type=credential.type,
            source=credential.source,
            credential_uri=credential.credential_uri,
            created_at=credential.created_at,
            updated_at=credential.updated_at,
            created_by=credential.created_by,
            updated_by=credential.updated_by
        )
