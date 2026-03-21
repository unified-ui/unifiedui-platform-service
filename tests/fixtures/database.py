"""Database fixtures for testing."""

import logging
import os
import tempfile
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.core.database.config import DatabaseConfig
from unifiedui.core.database.models import Base

logger = logging.getLogger(__name__)

# Test database - use a temporary file instead of :memory: to share between connections
_test_db_file: str | None = None


def get_test_db_url() -> str:
    """Get test database URL with temporary file."""
    global _test_db_file
    if _test_db_file is None:
        # Create a temporary file for the test database
        fd, _test_db_file = tempfile.mkstemp(suffix=".db")
        os.close(fd)  # Close the file descriptor, SQLite will open it
    return f"sqlite:///{_test_db_file}"


def cleanup_test_db() -> None:
    """Clean up test database file."""
    global _test_db_file
    if _test_db_file and os.path.exists(_test_db_file):
        try:
            os.unlink(_test_db_file)
        except Exception:
            pass  # Ignore cleanup errors
        _test_db_file = None


@pytest.fixture(scope="function")
def test_db_engine() -> Generator[Engine]:
    """Create a test database engine with SQLite file."""
    # Clean up any previous test database
    cleanup_test_db()

    TEST_DATABASE_URL = get_test_db_url()

    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},  # Needed for SQLite
        echo=False,
        execution_options={"schema_translate_map": {"unifiedui": None}},
    )

    # Create all tables
    logger.info(f"Creating tables, available tables before: {Base.metadata.tables.keys()}")
    Base.metadata.create_all(bind=engine)

    # Verify tables were created
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    logger.info(f"Tables created in test database: {tables}")

    yield engine

    # Clean up - truncate all tables and dispose engine
    with engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        conn.commit()

    engine.dispose()

    # Clean up the temporary file
    cleanup_test_db()


@pytest.fixture(scope="function")
def test_db_session(test_db_engine: Engine) -> Generator[Session]:
    """Create a test database session."""
    SessionLocal = sessionmaker(bind=test_db_engine)
    session = SessionLocal()

    yield session

    session.rollback()
    session.close()


@pytest.fixture(scope="function")
def test_db_client(test_db_engine: Engine) -> Generator[SQLAlchemyClient]:
    """Create a test database client with SQLite file."""
    TEST_DATABASE_URL = get_test_db_url()

    config = DatabaseConfig(database_url=TEST_DATABASE_URL)
    client = SQLAlchemyClient(config=config)

    # Replace engine and SessionLocal with test instances
    client.engine.dispose()  # Close the engine created in __init__
    client.engine = test_db_engine
    client.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)

    yield client

    client.close()
