"""Abstract base class for vault client."""
import os
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
import base64
import hashlib

from aihub.core.vault.vault import BaseVault
from aihub.logger import get_logger

logger = get_logger(__name__)


class BaseVaultClient(ABC):
    """
    Abstract base class for vault client.
    Provides secret management with optional encrypted caching.
    """

    def __init__(self, cache_client: Optional[Any] = None):
        """
        Initialize vault client.
        
        Args:
            cache_client: Optional cache client for caching encrypted secrets
        """
        self.cache_client = cache_client
        self._cipher = self._init_cipher()

    def _init_cipher(self) -> Optional[Fernet]:
        """
        Initialize cipher for secret encryption if key is available.
        
        Returns:
            Fernet cipher or None
        """
        encryption_key = os.getenv("SECRETS_ENCRYPTION_KEY")
        if not encryption_key:
            logger.info("SECRETS_ENCRYPTION_KEY not set - secrets will not be cached")
            return None
        
        try:
            # Derive a proper Fernet key from the encryption key
            key = base64.urlsafe_b64encode(
                hashlib.sha256(encryption_key.encode()).digest()
            )
            return Fernet(key)
        except Exception as e:
            logger.warning(f"Failed to initialize encryption cipher: {e}")
            return None

    def _encrypt_secret(self, secret: str) -> Optional[str]:
        """
        Encrypt a secret value.
        
        Args:
            secret: Secret to encrypt
            
        Returns:
            Encrypted secret or None if encryption not available
        """
        if not self._cipher:
            return None
        
        try:
            encrypted = self._cipher.encrypt(secret.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Failed to encrypt secret: {e}")
            return None

    def _decrypt_secret(self, encrypted_secret: str) -> Optional[str]:
        """
        Decrypt an encrypted secret.
        
        Args:
            encrypted_secret: Encrypted secret
            
        Returns:
            Decrypted secret or None if decryption fails
        """
        if not self._cipher:
            return None
        
        try:
            decrypted = self._cipher.decrypt(encrypted_secret.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt secret: {e}")
            return None

    @abstractmethod
    def get_vault(self) -> BaseVault:
        """
        Get the underlying vault instance.
        
        Returns:
            BaseVault instance
        """
        pass

    def store_secret(
        self,
        key: str,
        value: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store a secret in the vault.
        
        Args:
            key: Secret key/name
            value: Secret value to store
            metadata: Optional metadata
            
        Returns:
            URI/reference to the stored secret
        """
        return self.get_vault().store_secret(key, value, metadata)

    def get_secret(self, uri: str, use_cache: bool = True) -> Optional[str]:
        """
        Retrieve a secret from vault with optional encrypted caching.
        
        Args:
            uri: URI/reference to the secret
            use_cache: Whether to use caching
            
        Returns:
            Secret value or None
        """
        # Check cache first if encryption is available
        if use_cache and self.cache_client and self._cipher:
            cache_key = f"vault:secret:{uri}"
            try:
                cached_encrypted = self.cache_client.get(cache_key)
                if cached_encrypted:
                    decrypted = self._decrypt_secret(cached_encrypted)
                    if decrypted:
                        logger.debug(f"Returning cached secret for {uri}")
                        return decrypted
            except Exception as e:
                logger.warning(f"Failed to get cached secret: {e}")
        
        # Fetch from vault
        secret = self.get_vault().get_secret(uri)
        
        # Cache encrypted secret if available
        if secret and self.cache_client and self._cipher:
            try:
                encrypted = self._encrypt_secret(secret)
                if encrypted:
                    cache_key = f"vault:secret:{uri}"
                    self.cache_client.set(cache_key, encrypted, ttl=3600)  # Cache for 1 hour
                    logger.debug(f"Cached encrypted secret for {uri}")
            except Exception as e:
                logger.warning(f"Failed to cache secret: {e}")
        
        return secret

    def update_secret(
        self,
        uri: str,
        value: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update a secret in the vault and invalidate cache.
        
        Args:
            uri: URI/reference to the secret
            value: New secret value
            metadata: Optional metadata
            
        Returns:
            True if updated successfully
        """
        success = self.get_vault().update_secret(uri, value, metadata)
        
        # Invalidate cache
        if success and self.cache_client:
            try:
                cache_key = f"vault:secret:{uri}"
                self.cache_client.delete(cache_key)
                logger.debug(f"Invalidated cache for secret {uri}")
            except Exception as e:
                logger.warning(f"Failed to invalidate secret cache: {e}")
        
        return success

    def delete_secret(self, uri: str) -> bool:
        """
        Delete a secret from the vault and invalidate cache.
        
        Args:
            uri: URI/reference to the secret
            
        Returns:
            True if deleted successfully
        """
        success = self.get_vault().delete_secret(uri)
        
        # Invalidate cache
        if success and self.cache_client:
            try:
                cache_key = f"vault:secret:{uri}"
                self.cache_client.delete(cache_key)
                logger.debug(f"Invalidated cache for deleted secret {uri}")
            except Exception as e:
                logger.warning(f"Failed to invalidate secret cache: {e}")
        
        return success

    def ping(self) -> bool:
        """Check if vault connection is alive."""
        return self.get_vault().ping()

    def close(self) -> None:
        """Close vault connection."""
        self.get_vault().close()
