"""Database configuration for SQLAlchemy."""

import os
from urllib.parse import quote_plus


class DatabaseConfig:
    """Configuration for database connection."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
        user: str | None = None,
        password: str | None = None,
        database_url: str | None = None,
        db_type: str | None = None,
    ):
        """
        Initialize database configuration.

        Args:
            host: Database host (default: localhost)
            port: Database port (default: 5432 for PostgreSQL, 1433 for MSSQL)
            database: Database name (default: unifiedui)
            user: Database user (default: unifiedui)
            password: Database password
            database_url: Complete database URL (overrides other params)
            db_type: Database type: 'postgresql' or 'mssql' (default: postgresql)
        """
        if database_url:
            self.database_url = database_url
        else:
            self.db_type = db_type or os.getenv("DB_TYPE", "postgresql")
            self.host = host or os.getenv("DB_HOST", "localhost")
            self.database = database or os.getenv("DB_NAME", "unifiedui")
            self.user = user or os.getenv("DB_USER", "unifiedui")
            self.password = password or os.getenv("DB_PASSWORD") or "unifiedui_password"

            if self.db_type == "mssql":
                self.port = port or int(os.getenv("DB_PORT", "1433"))
                # URL-encode the password for special characters
                encoded_password = quote_plus(self.password)
                # MSSQL connection string with pyodbc
                self.database_url = (
                    f"mssql+pyodbc://{self.user}:{encoded_password}@{self.host}:{self.port}/{self.database}"
                    f"?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
                )
            else:
                self.port = port or int(os.getenv("DB_PORT", "5432"))
                self.database_url = f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

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
