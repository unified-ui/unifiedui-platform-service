from logging.config import fileConfig
import os
from urllib.parse import quote_plus

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy import text

from alembic import context

from unifiedui.core.database.models import Base
from unifiedui.core.database.models import HighPrecisionDateTime

config = context.config


def get_database_url() -> str | None:
    """Construct database URL from environment variables."""
    if os.getenv("DATABASE_URL"):
        return os.getenv("DATABASE_URL")

    db_host = os.getenv("DB_HOST")
    if not db_host:
        return None

    db_type = os.getenv("DB_TYPE", "postgresql")
    db_port = os.getenv("DB_PORT", "5432" if db_type == "postgresql" else "1433")
    db_name = os.getenv("DB_NAME", "unifiedui")
    db_user = os.getenv("DB_USER", "unifiedui")
    db_password = os.getenv("DB_PASSWORD", "")

    if db_type == "mssql":
        encoded_password = quote_plus(db_password)
        return (
            f"mssql+pyodbc://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}"
            f"?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
        )
    else:
        return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


database_url = get_database_url()
if database_url:
    escaped_url = database_url.replace("%", "%%")
    config.set_main_option("sqlalchemy.url", escaped_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def render_item(type_, obj, autogen_context):
    """Render custom types with short names instead of full module paths."""
    if type_ == "type" and isinstance(obj, HighPrecisionDateTime):
        autogen_context.imports.add(
            "from unifiedui.core.database.models import HighPrecisionDateTime"
        )
        return "HighPrecisionDateTime()"
    return False


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        version_table_schema="unifiedui",
        render_item=render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Create schema BEFORE configuring Alembic context
        # This ensures version_table_schema exists before Alembic tries to access it
        db_type = os.getenv("DB_TYPE", "postgresql")
        if db_type == "mssql":
            connection.execute(text(
                "IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = 'unifiedui') "
                "EXEC('CREATE SCHEMA unifiedui')"
            ))
        else:
            connection.execute(text("CREATE SCHEMA IF NOT EXISTS unifiedui"))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            version_table_schema="unifiedui",
            render_item=render_item,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
