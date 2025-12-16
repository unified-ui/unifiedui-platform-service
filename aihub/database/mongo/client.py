from pymongo import MongoClient
from pymongo.database import Database

from aihub.core.database.base import BaseDatabaseClient
from aihub.database.mongo.collections.tenants import MongoDBTenantsCollection
from aihub.database.mongo.collections.permissions import MongoDBPermissionsCollection
from aihub.database.mongo.collections.custom_groups import MongoDBCustomGroupsCollection


class MongoDBDatabaseClient(BaseDatabaseClient):
    """MongoDB implementation of the database client."""

    def __init__(self, connection_string: str, database_name: str):
        self._connection_string = connection_string
        self._database_name = database_name
        self._client: MongoClient = None
        self._db: Database = None
        self._tenants_collection = None
        self._custom_groups_collection = None

    def connect(self) -> None:
        """Establish database connection."""
        self._client = MongoClient(self._connection_string)
        self._db = self._client[self._database_name]

    def disconnect(self) -> None:
        """Close database connection."""
        if self._client is not None:
            self._client.close()
            self._client = None
            self._db = None
            self._tenants_collection = None

    def health_check(self) -> bool:
        """Check if database connection is healthy."""
        try:
            if self._client is not None:
                # Ping the database
                self._client.admin.command('ping')
                return True
            return False
        except Exception:
            return False

    def tenants(self) -> MongoDBTenantsCollection:
        """Get the tenants collection."""
        if self._db is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        
        if self._tenants_collection is None:
            self._tenants_collection = MongoDBTenantsCollection(self._db)
        
        return self._tenants_collection

    def permissions(self) -> MongoDBPermissionsCollection:
        """Get the permissions collection."""
        if self._db is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        
        return MongoDBPermissionsCollection(self._db)

    def custom_groups(self) -> MongoDBCustomGroupsCollection:
        """Get the custom groups collection."""
        if self._db is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        
        if self._custom_groups_collection is None:
            self._custom_groups_collection = MongoDBCustomGroupsCollection(self._db["custom_groups"])
        
        return self._custom_groups_collection
