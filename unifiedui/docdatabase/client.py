'''
import os
from typing import Optional

from unifiedui.core.docdatabase.base import BaseDatabaseClient
from unifiedui.docdatabase.enums import DocumentDatabaseTypeEnum
from unifiedui.docdatabase.mongo.client import MongoDBDatabaseClient
from unifiedui.core.docdatabase.collections.tenants import TenantsCollection
from unifiedui.core.docdatabase.collections.permissions import PermissionsCollection
from unifiedui.core.docdatabase.collections.custom_groups import CustomGroupsCollection


class DatabaseClient:
    """
    Main database client wrapper that provides access to collections
    via properties. This class wraps the underlying database-specific
    client (MongoDB, Cosmos DB, etc.) and provides a unified interface.
    """

    def __init__(self, client: BaseDatabaseClient):
        """
        Initialize the database client wrapper.

        Args:
            client: The underlying database-specific client
        """
        self._client = client

    @property
    def tenants(self) -> TenantsCollection:
        """
        Get the tenants collection.

        Returns:
            TenantsCollection: The tenants collection interface
        """
        return self._client.tenants()

    @property
    def permissions(self) -> PermissionsCollection:
        """
        Get the permissions collection.

        Returns:
            PermissionsCollection: The permissions collection interface
        """
        return self._client.permissions()

    @property
    def custom_groups(self) -> CustomGroupsCollection:
        """
        Get the custom groups collection.

        Returns:
            CustomGroupsCollection: The custom groups collection interface
        """
        return self._client.custom_groups()

    def health_check(self) -> bool:
        """
        Check if database connection is healthy.

        Returns:
            bool: True if healthy, False otherwise
        """
        return self._client.health_check()

    def disconnect(self) -> None:
        """Close the database connection."""
        self._client.disconnect()


class DatabaseClientFactory:
    """
    Factory class for creating database clients based on the database type.
    Supports MongoDB and Cosmos DB.
    """

    @staticmethod
    def create(
        db_type: Optional[DocumentDatabaseTypeEnum] = None,
        connection_string: Optional[str] = None,
        database_name: Optional[str] = None
    ) -> DatabaseClient:
        """
        Create a database client based on the specified type.

        Args:
            db_type: Type of database (MONGO_DB or COSMOS_DB).
                     If not provided, reads from DOCUMENT_DATABASE env var.
            connection_string: Database connection string.
                               If not provided, reads from environment variables.
            database_name: Name of the database.
                           If not provided, reads from environment variables.

        Returns:
            An instance of DatabaseClient wrapping the specific implementation.

        Raises:
            ValueError: If db_type is invalid or not supported.
            RuntimeError: If required configuration is missing.
        """
        # Determine database type
        if db_type is None:
            db_type_str = os.getenv("DOCUMENT_DATABASE")
            if not db_type_str:
                raise RuntimeError(
                    "DOCUMENT_DATABASE environment variable is not set. "
                    "Please set it to 'MONGO_DB' or 'COSMOS_DB'."
                )
            try:
                db_type = DocumentDatabaseTypeEnum(db_type_str)
            except ValueError:
                raise ValueError(
                    f"Invalid DOCUMENT_DATABASE value: {db_type_str}. "
                    f"Valid values are: {', '.join([e.value for e in DocumentDatabaseTypeEnum])}"
                )

        # Create underlying client based on type
        if db_type == DocumentDatabaseTypeEnum.MONGO_DB:
            underlying_client = DatabaseClientFactory._create_mongodb_client(
                connection_string, database_name
            )
        elif db_type == DocumentDatabaseTypeEnum.COSMOS_DB:
            raise NotImplementedError(
                "Cosmos DB client is not yet implemented. "
                "Please use MONGO_DB for now."
            )
        else:
            raise ValueError(f"Unsupported database type: {db_type}")

        # Wrap in DatabaseClient
        return DatabaseClient(underlying_client)

    @staticmethod
    def _create_mongodb_client(
        connection_string: Optional[str] = None,
        database_name: Optional[str] = None
    ) -> MongoDBDatabaseClient:
        """Create a MongoDB client with the given configuration."""
        # Get connection string
        if connection_string is None:
            connection_string = os.getenv("MONGODB_CONNECTION_STRING")
            if not connection_string:
                raise RuntimeError(
                    "MongoDB connection string not provided. "
                    "Set MONGODB_CONNECTION_STRING environment variable."
                )

        # Get database name
        if database_name is None:
            database_name = os.getenv("MONGODB_DATABASE_NAME", "unifiedui")

        client = MongoDBDatabaseClient(
            connection_string=connection_string,
            database_name=database_name
        )

        # Establish connection
        client.connect()

        return client


# Convenience function for creating a database client
def get_database_client(
    db_type: Optional[DocumentDatabaseTypeEnum] = None
) -> DatabaseClient:
    """
    Convenience function to create and return a database client.

    Usage:
        # Using environment variables
        db_client = get_database_client()

        # Explicitly specifying type
        db_client = get_database_client(DocumentDatabaseTypeEnum.MONGO_DB)
    """
    return DatabaseClientFactory.create(db_type=db_type)
'''
