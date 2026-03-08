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
    identity_client_secret: str | None = None
    identity_tenant_id: str | None = None
    identity_jwks_url: str = "https://login.microsoftonline.com/common/discovery/v2.0/keys"
    identity_token_algorithms: list[str] = ["RS256"]
    identity_verify_signature: bool = True

    # Google Identity Configuration
    google_client_id: str | None = None
    google_service_account_token: str | None = None

    # AWS Cognito Identity Configuration
    aws_cognito_region: str | None = None
    aws_cognito_user_pool_id: str | None = None
    aws_cognito_client_id: str | None = None
    aws_cognito_access_key_id: str | None = None
    aws_cognito_secret_access_key: str | None = None

    # LDAP Identity Configuration
    ldap_server_url: str | None = None
    ldap_bind_dn: str | None = None
    ldap_bind_password: str | None = None
    ldap_base_dn: str | None = None
    ldap_user_search_filter: str = "(objectClass=person)"
    ldap_group_search_filter: str = "(objectClass=groupOfNames)"
    ldap_use_ssl: bool = True

    # Kerberos Identity Configuration
    kerberos_realm: str | None = None
    kerberos_kdc_host: str | None = None
    kerberos_service_principal: str | None = None
    kerberos_keytab_path: str | None = None
    kerberos_ldap_url: str | None = None
    kerberos_ldap_base_dn: str | None = None

    # SAML Identity Configuration
    saml_entity_id: str | None = None
    saml_sso_url: str | None = None
    saml_certificate: str | None = None
    saml_metadata_url: str | None = None
    saml_attribute_map_id: str = "uid"
    saml_attribute_map_email: str = "email"
    saml_attribute_map_display_name: str = "displayName"
    saml_attribute_map_first_name: str = "firstName"
    saml_attribute_map_last_name: str = "lastName"

    # Okta Identity Configuration
    okta_domain: str | None = None
    okta_client_id: str | None = None
    okta_api_token: str | None = None
    okta_authorization_server_id: str = "default"

    # Generic OIDC Identity Configuration
    oidc_issuer_url: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_jwks_url: str | None = None
    oidc_userinfo_url: str | None = None
    oidc_scopes: str = "openid profile email"

    # Deployment Mode
    deployment_mode: str = "self-hosted"
    system_admin_email: str | None = None

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
