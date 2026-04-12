"""Script to clean up MSSQL schema for fresh migration."""

import os
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text


def main():
    """Drop all objects in unifiedui schema and recreate it."""
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT", "1433")
    db_name = os.getenv("DB_NAME", "unifiedui")
    db_user = os.getenv("DB_USER", "sqladmin")
    db_password = os.getenv("DB_PASSWORD", "")

    encoded_password = quote_plus(db_password)
    url = (
        f"mssql+pyodbc://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}"
        f"?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
    )

    engine = create_engine(url)
    with engine.connect() as conn:
        # Drop all foreign keys first
        fks = conn.execute(
            text("""
            SELECT 'ALTER TABLE unifiedui.' + QUOTENAME(t.name) +
                   ' DROP CONSTRAINT ' + QUOTENAME(fk.name) + ';'
            FROM sys.foreign_keys fk
            JOIN sys.tables t ON fk.parent_object_id = t.object_id
            WHERE t.schema_id = SCHEMA_ID('unifiedui')
        """)
        )
        for row in fks:
            try:
                conn.execute(text(row[0]))
            except Exception as e:
                print(f"FK drop failed: {e}")

        # Drop all tables
        tables = conn.execute(
            text("""
            SELECT 'DROP TABLE unifiedui.' + QUOTENAME(name) + ';'
            FROM sys.tables WHERE schema_id = SCHEMA_ID('unifiedui')
        """)
        )
        for row in tables:
            try:
                conn.execute(text(row[0]))
            except Exception as e:
                print(f"Table drop failed: {e}")

        # Drop all check constraints (used for enums)
        constraints = conn.execute(
            text("""
            SELECT 'ALTER TABLE unifiedui.' + QUOTENAME(t.name) +
                   ' DROP CONSTRAINT ' + QUOTENAME(cc.name) + ';'
            FROM sys.check_constraints cc
            JOIN sys.tables t ON cc.parent_object_id = t.object_id
            WHERE t.schema_id = SCHEMA_ID('unifiedui')
        """)
        )
        for row in constraints:
            try:
                conn.execute(text(row[0]))
            except Exception as e:
                print(f"Constraint drop failed: {e}")

        conn.commit()

        # Drop schema
        try:
            conn.execute(text("DROP SCHEMA IF EXISTS unifiedui"))
            conn.commit()
            print("Schema dropped successfully")
        except Exception as e:
            print(f"Schema drop failed: {e}")


if __name__ == "__main__":
    main()
