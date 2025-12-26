"""Database configuration for SQLAlchemy."""
import os
from typing import Optional


class DatabaseConfig:
    """Configuration for database connection."""
    
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database_url: Optional[str] = None
    ):
        """
        Initialize database configuration.
        
        Args:
            host: Database host (default: localhost)
            port: Database port (default: 5432)
            database: Database name (default: aihub)
            user: Database user (default: aihub)
            password: Database password
            database_url: Complete database URL (overrides other params)
        """
        if database_url:
            self.database_url = database_url
        else:
            self.host = host or os.getenv("DB_HOST", "localhost")
            self.port = port or int(os.getenv("DB_PORT", "5432"))
            self.database = database or os.getenv("DB_NAME", "aihub")
            self.user = user or os.getenv("DB_USER", "aihub")
            self.password = password or os.getenv("DB_PASSWORD", "aihub_password")
            
            self.database_url = (
                f"postgresql://{self.user}:{self.password}"
                f"@{self.host}:{self.port}/{self.database}"
            )
    
    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """
        Create database configuration from environment variables.
        
        Returns:
            DatabaseConfig instance
        """
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            return cls(database_url=database_url)
        
        return cls()
