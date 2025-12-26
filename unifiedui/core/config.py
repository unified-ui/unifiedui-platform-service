"""Application configuration using Pydantic Settings."""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # PostgreSQL Database Configuration
    database_url: Optional[str] = None
    db_host: Optional[str] = None
    db_port: Optional[int] = None
    db_name: Optional[str] = None
    db_user: Optional[str] = None
    db_password: Optional[str] = None
    
    # MongoDB Configuration (Optional)
    document_database: Optional[str] = None
    mongodb_connection_string: Optional[str] = None
    mongodb_database_name: str = "aihub"
    
    # Cache Configuration (Optional)
    cache_enabled: bool = False
    cache_backend: Optional[str] = None
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    cache_default_ttl: int = 3600  # 1 hour
    
    # RabbitMQ Configuration (Optional)
    rabbitmq_host: Optional[str] = None
    rabbitmq_port: Optional[int] = None
    rabbitmq_management_port: Optional[int] = None
    rabbitmq_user: Optional[str] = None
    rabbitmq_password: Optional[str] = None
    
    # HashiCorp Vault Configuration (Optional)
    vault_addr: Optional[str] = None
    vault_token: Optional[str] = None
    
    # Azure KeyVault Configuration (Optional)
    azure_keyvault_vault_name: Optional[str] = None
    
    # Vault Type Selection
    vault_type: Optional[str] = None  # AZURE_KEYVAULT or HASHICORP_VAULT
    
    # Secret Encryption Key (for caching secrets)
    secrets_encryption_key: Optional[str] = None
    
    # API Configuration
    api_title: str = "unified-ui API"
    api_description: str = "unified-ui - AI Application Management Platform"
    api_version: str = "1.0.0"
    
    # CORS Configuration
    cors_origins: list[str] = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]
    
    # Logging Configuration
    log_level: str = "INFO"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Ignore extra fields for forward compatibility
    )


# Global settings instance
settings = Settings()
