"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # PostgreSQL Database Configuration
    database_url: str | None = None
    db_host: str | None = None
    db_port: int | None = None
    db_name: str | None = None
    db_user: str | None = None
    db_password: str | None = None

    # MongoDB Configuration (Optional)
    document_database: str | None = None
    mongodb_connection_string: str | None = None
    mongodb_database_name: str = "unifiedui"

    # Cache Configuration (Optional)
    cache_enabled: bool = False
    cache_backend: str | None = None
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None
    cache_default_ttl: int = 3600  # 1 hour

    # RabbitMQ Configuration (Optional)
    rabbitmq_host: str | None = None
    rabbitmq_port: int | None = None
    rabbitmq_management_port: int | None = None
    rabbitmq_user: str | None = None
    rabbitmq_password: str | None = None

    # Vault Type Selection
    vault_type: str | None = None  # AZURE_KEYVAULT, HASHICORP_VAULT, or DOTENV
    app_vault_type: str | None = None  # Override vault type for app service keys (defaults to vault_type)
    secrets_vault_type: str | None = None  # Override vault type for credential secrets (defaults to vault_type)

    # App Vault Configuration (service-to-service keys)
    app_hashicorp_vault_addr: str | None = None
    app_hashicorp_vault_token: str | None = None
    app_azure_keyvault_url: str | None = None

    # Secrets Vault Configuration (credential secrets)
    secrets_hashicorp_vault_addr: str | None = None
    secrets_hashicorp_vault_token: str | None = None
    secrets_azure_keyvault_url: str | None = None

    # Secret Encryption Key (for caching secrets)
    secrets_encryption_key: str | None = None

    # Service-to-Service Authentication Keys
    x_agent_service_key: str | None = None  # DEPRECATED: use app vault instead

    # App Vault Key Names (logical key names used to retrieve service keys from vault)
    app_vault_agent_to_platform_key: str = "AGENT_TO_PLATFORM_SERVICE_KEY"
    app_vault_platform_to_agent_key: str = "PLATFORM_TO_AGENT_SERVICE_KEY"

    # Agent Service Configuration
    agent_service_url: str = "http://localhost:8085"
    agent_service_timeout: int = 30

    # API Configuration
    api_title: str = "unified-ui API"
    api_description: str = "unified-ui - AI Agent Management Platform"
    api_version: str = "1.0.0"

    # CORS Configuration
    cors_origins: list[str] = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = [
        "Authorization",
        "Content-Type",
        "Accept",
        "X-Service-Key",
        "X-Request-ID",
        "X-Correlation-ID",
        "X-Unified-UI-Autonomous-Agent-API-Key",
        "X-Use-Cache",
        "Cache-Control",
    ]

    # Identity / Token Validation
    identity_client_id: str | None = None
    identity_jwks_url: str = "https://login.microsoftonline.com/common/discovery/v2.0/keys"
    identity_token_algorithms: list[str] = ["RS256"]
    identity_verify_signature: bool = True

    # Logging Configuration
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields for forward compatibility
    )


# Global settings instance
settings = Settings()
