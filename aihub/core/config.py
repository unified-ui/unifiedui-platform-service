"""Application configuration using Pydantic Settings."""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database Configuration
    document_database: str
    mongodb_connection_string: str
    mongodb_database_name: str = "aihub"
    
    # API Configuration
    api_title: str = "AIHub API"
    api_description: str = "AIHub - AI Application Management Platform"
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
        case_sensitive=False
    )


# Global settings instance
settings = Settings()
