"""Business logic handlers for credential operations."""
import uuid
from typing import Optional, List

from sqlalchemy import select, or_

from aihub.core.database.client import SQLAlchemyClient
from aihub.core.database.models import Credential, CredentialMember, CredentialMemberPermission
from aihub.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from aihub.core.identity.users import ContextIdentityUser
from aihub.core.vault.client import BaseVaultClient
from aihub.caching.client import CacheClient
from aihub.schema.requests.credentials import CreateCredentialRequest, UpdateCredentialRequest
from aihub.schema.requests.credential_permissions import SetCredentialPermissionRequest
from aihub.schema.responses.credentials import CredentialResponse
from aihub.schema.responses.credential_permissions import (
    CredentialPermissionResponse,
    CredentialPrincipalsResponse,
    PrincipalPermissionsResponse
)
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
        user: ContextIdentityUser,
        skip: int = 0,
        limit: int = 100,
        name_filter: Optional[str] = None,
        use_cache: bool = True
    ) -> List[CredentialResponse]:
        """
        Get a list of credentials for a tenant (filtered by permissions).
        
        Args:
            tenant_id: The ID of the tenant
            user: ContextIdentityUser object for permission checking (required)
            skip: Number of items to skip
            limit: Maximum number of items to return
            name_filter: Optional filter by credential name
            use_cache: Whether to use caching
            
        Returns:
            List of credential responses (without secret values)
        """
        from aihub.core.database.enums import TenantPermissionEnum
        
        logger.info("Listing credentials", extra={"tenant_id": tenant_id, "skip": skip, "limit": limit})
        
        # Check if user is admin (has GLOBAL_ADMIN or CREDENTIALS_ADMIN)
        user_id = user.identity.get_id()
        user_tenants = user.tenants
        matching_tenant = next(
            (t for t in user_tenants if t["tenant"]["id"] == tenant_id),
            None
        )
        
        is_admin = False
        if matching_tenant:
            user_permissions = matching_tenant["permissions"]
            admin_permissions = [
                TenantPermissionEnum.GLOBAL_ADMIN.value,
                TenantPermissionEnum.CREDENTIALS_ADMIN.value
            ]
            is_admin = any(perm in user_permissions for perm in admin_permissions)
        
        # Only get group IDs if not admin
        identity_group_ids = None
        custom_group_ids = None
        if not is_admin:
            identity_group_ids = [g.id for g in user.groups]
            custom_group_ids = [g.id for g in user.custom_groups]
        
        # Build cache key
        filter_key = name_filter or "all"
        cache_key = f"credentials:list:tenant:{tenant_id}:user:{user_id}:skip:{skip}:limit:{limit}:filter:{filter_key}"
        
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
            if not is_admin:
                # Build permission filter
                principal_ids = [user_id]
                if identity_group_ids:
                    principal_ids.extend(identity_group_ids)
                if custom_group_ids:
                    principal_ids.extend(custom_group_ids)
                
                # Subquery for credentials where user is a member
                member_subquery = (
                    select(CredentialMember.credential_id)
                    .where(
                        CredentialMember.tenant_id == tenant_id,
                        CredentialMember.principal_id.in_(principal_ids)
                    )
                    .distinct()
                )
                
                query = query.where(Credential.id.in_(member_subquery))
            
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
        logger.info("Creating credential", extra={"tenant_id": tenant_id, "credential_name": request.name, "user_id": user_id})
        
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
                source=request.source,
                credential_uri=vault_uri,
                created_by=user_id,
                updated_by=user_id
            )
            session.add(credential)
            session.flush()  # Flush to get auto-generated timestamps
            
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
    ) -> CredentialPrincipalsResponse:
        """
        List all permissions for a credential.
        
        Args:
            tenant_id: The ID of the tenant
            credential_id: The ID of the credential
            
        Returns:
            Grouped permissions by principal
            
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
            
            # Get all members with their permissions
            member_query = select(CredentialMember).where(
                CredentialMember.credential_id == credential_id,
                CredentialMember.tenant_id == tenant_id
            )
            members = session.execute(member_query).scalars().all()
            
            # Group permissions by principal
            principals_map = {}
            for member in members:
                # Get permissions for this member
                perm_query = select(CredentialMemberPermission).where(
                    CredentialMemberPermission.credential_member_id == member.id
                )
                member_permissions = session.execute(perm_query).scalars().all()
                
                # Group by principal
                if member.principal_id not in principals_map:
                    principals_map[member.principal_id] = {
                        "credential_id": credential_id,
                        "tenant_id": tenant_id,
                        "principal_id": member.principal_id,
                        "principal_type": member.principal_type,
                        "permissions": []
                    }
                
                # Add permissions
                for perm in member_permissions:
                    principals_map[member.principal_id]["permissions"].append(perm.permission.value if hasattr(perm.permission, 'value') else perm.permission)
            
            # Convert to list of principals
            principals = [
                PrincipalPermissionsResponse(**principal_data)
                for principal_data in principals_map.values()
            ]
            
            logger.info("Retrieved credential permissions", extra={"count": len(principals)})
            return CredentialPrincipalsResponse(
                credential_id=credential_id,
                tenant_id=tenant_id,
                principals=principals
            )

    def get_credential_permission(
        self,
        tenant_id: str,
        credential_id: str,
        principal_id: str
    ) -> PrincipalPermissionsResponse:
        """
        Get all permissions for a specific principal on a credential.
        
        Args:
            tenant_id: The ID of the tenant
            credential_id: The ID of the credential
            principal_id: The ID of the principal
            
        Returns:
            Principal with all their permissions
            
        Raises:
            CredentialNotFoundError: If credential or principal not found
        """
        logger.info("Getting credential permissions for principal", extra={
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
            
            # Get member
            member_query = select(CredentialMember).where(
                CredentialMember.credential_id == credential_id,
                CredentialMember.tenant_id == tenant_id,
                CredentialMember.principal_id == principal_id
            )
            member = session.execute(member_query).scalar_one_or_none()
            
            if not member:
                raise CredentialNotFoundError(f"Member with principal {principal_id} not found")
            
            # Get all permissions for this member
            perm_query = select(CredentialMemberPermission).where(
                CredentialMemberPermission.credential_member_id == member.id
            )
            permissions = session.execute(perm_query).scalars().all()
            
            if not permissions:
                raise CredentialNotFoundError(f"No permissions for principal {principal_id}")
            
            # Build response with all permissions
            permission_list = [
                perm.permission.value if hasattr(perm.permission, 'value') else perm.permission
                for perm in permissions
            ]
            
            return PrincipalPermissionsResponse(
                credential_id=credential_id,
                tenant_id=tenant_id,
                principal_id=member.principal_id,
                principal_type=member.principal_type,
                permissions=permission_list
            )

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
            
            # Check if member already exists
            member_query = select(CredentialMember).where(
                CredentialMember.credential_id == credential_id,
                CredentialMember.tenant_id == tenant_id,
                CredentialMember.principal_id == request.principal_id,
                CredentialMember.principal_type == request.principal_type
            )
            member = session.execute(member_query).scalar_one_or_none()
            
            if not member:
                # Create new member
                member = CredentialMember(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    credential_id=credential_id,
                    principal_id=request.principal_id,
                    principal_type=request.principal_type,
                    name=f"{request.principal_type.value}_{request.principal_id}",
                    description=f"Member {request.principal_type.value}"
                )
                session.add(member)
                session.flush()
                logger.info("Created credential member")
            
            # Check if permission already exists for this member
            perm_query = select(CredentialMemberPermission).where(
                CredentialMemberPermission.credential_member_id == member.id,
                CredentialMemberPermission.permission == request.permission
            )
            permission = session.execute(perm_query).scalar_one_or_none()
            
            if not permission:
                # Create new permission
                permission = CredentialMemberPermission(
                    id=str(uuid.uuid4()),
                    credential_member_id=member.id,
                    permission=request.permission,
                    name=f"{request.permission.value}_permission",
                    description=f"Permission for {request.principal_type.value}"
                )
                session.add(permission)
                logger.info("Created credential permission")
            
            session.flush()  # Flush to get auto-generated timestamps
            
            # Invalidate caches
            if self.cache_client:
                try:
                    self._invalidate_list_cache(tenant_id)
                    logger.debug("Invalidated credential list cache")
                except Exception as e:
                    logger.warning(f"Failed to invalidate cache: {e}")
            
            return self._permission_to_response(member, permission)

    def delete_credential_permission(
        self,
        tenant_id: str,
        credential_id: str,
        principal_id: str,
        principal_type: str,
        permission: str
    ) -> None:
        """
        Delete a specific credential permission.
        
        Args:
            tenant_id: The ID of the tenant
            credential_id: The ID of the credential
            principal_id: The ID of the principal
            principal_type: The type of the principal (IDENTITY_USER, IDENTITY_GROUP, CUSTOM_GROUP)
            permission: The specific permission to delete (READ, WRITE, ADMIN)
            
        Raises:
            CredentialNotFoundError: If credential, member, or permission not found
        """
        logger.info("Deleting credential permission", extra={
            "tenant_id": tenant_id,
            "credential_id": credential_id,
            "principal_id": principal_id,
            "principal_type": principal_type,
            "permission": permission
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
            
            # Get member
            member_query = select(CredentialMember).where(
                CredentialMember.credential_id == credential_id,
                CredentialMember.tenant_id == tenant_id,
                CredentialMember.principal_id == principal_id,
                CredentialMember.principal_type == principal_type
            )
            member = session.execute(member_query).scalar_one_or_none()
            
            if not member:
                raise CredentialNotFoundError(f"Member with principal {principal_id} not found")
            
            # Get and delete the specific permission
            perm_query = select(CredentialMemberPermission).where(
                CredentialMemberPermission.credential_member_id == member.id,
                CredentialMemberPermission.permission == permission
            )
            perm = session.execute(perm_query).scalar_one_or_none()
            
            if not perm:
                raise CredentialNotFoundError(f"Permission {permission} not found for principal {principal_id}")
            
            session.delete(perm)
            
            # Check if member has any remaining permissions
            remaining_perms_query = select(CredentialMemberPermission).where(
                CredentialMemberPermission.credential_member_id == member.id
            )
            remaining_perms = session.execute(remaining_perms_query).scalars().all()
            
            # If no permissions left, delete the member too
            if not remaining_perms:
                session.delete(member)
                logger.info("Deleted member as no permissions remain")
            
            # Invalidate caches
            if self.cache_client:
                try:
                    self._invalidate_list_cache(tenant_id)
                    logger.debug("Invalidated credential list cache")
                except Exception as e:
                    logger.warning(f"Failed to invalidate cache: {e}")
            
            logger.info("Deleted credential permission")

    @staticmethod
    def _permission_to_response(member: CredentialMember, permission: CredentialMemberPermission) -> CredentialPermissionResponse:
        """Convert CredentialMember and CredentialMemberPermission to response."""
        return CredentialPermissionResponse(
            id=permission.id,
            credential_id=member.credential_id,
            tenant_id=member.tenant_id,
            principal_id=member.principal_id,
            principal_type=member.principal_type,
            action=permission.permission,
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
