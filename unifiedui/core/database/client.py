"""SQLAlchemy database client for PostgreSQL."""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from unifiedui.core.database.config import DatabaseConfig
from unifiedui.core.database.models import Base
from unifiedui.logger import get_logger

logger = get_logger(__name__)


class SQLAlchemyClient:
    """SQLAlchemy database client."""

    def __init__(
        self,
        config: DatabaseConfig | None = None,
        echo: bool = False,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout: int = 30,
        pool_recycle: int = 3600,
    ):
        """
        Initialize SQLAlchemy client.

        Args:
            config: Database configuration (if None, loads from environment)
            echo: Enable SQLAlchemy query logging
            pool_size: Number of connections to maintain in pool
            max_overflow: Maximum overflow connections
            pool_timeout: Connection timeout in seconds
            pool_recycle: Connection recycle time in seconds
        """
        self.config = config or DatabaseConfig.from_env()

        logger.info(
            "Initializing database engine", extra={"database_url": self._mask_password(self.config.database_url)}
        )

        self.engine = create_engine(
            self.config.database_url,
            echo=echo,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
            pool_pre_ping=True,  # Verify connections before using them
        )

        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        logger.info("Database engine initialized successfully")

    @staticmethod
    def _mask_password(url: str) -> str:
        """Mask password in database URL for logging."""
        if "@" in url and ":" in url:
            parts = url.split("@")
            if len(parts) == 2:
                credentials = parts[0].split("://")
                if len(credentials) == 2:
                    user_pass = credentials[1].split(":")
                    if len(user_pass) == 2:
                        return f"{credentials[0]}://{user_pass[0]}:****@{parts[1]}"
        return url

    @contextmanager
    def get_session(self) -> Generator[Session]:
        """
        Get a database session with automatic cleanup.

        Yields:
            Database session

        Example:
            with db_client.get_session() as session:
                tenant = session.query(Tenant).filter_by(id=tenant_id).first()
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error("Session error: %s", e, exc_info=True)
            raise
        finally:
            session.close()

    def get_session_direct(self) -> Session:
        """
        Get a database session directly (caller is responsible for closing).

        Returns:
            Database session

        Note:
            Caller must close the session manually. Prefer using get_session()
            context manager when possible.
        """
        return self.SessionLocal()

    def create_all_tables(self):
        """Create all tables defined in models."""
        logger.info("Creating all database tables")
        Base.metadata.create_all(bind=self.engine)
        logger.info("All tables created successfully")

    def drop_all_tables(self):
        """Drop all tables. Use with caution!"""
        logger.warning("Dropping all database tables")
        Base.metadata.drop_all(bind=self.engine)
        logger.warning("All tables dropped")

    def close(self):
        """Close all connections and dispose engine."""
        logger.info("Closing database engine")
        self.engine.dispose()
        logger.info("Database engine closed")
