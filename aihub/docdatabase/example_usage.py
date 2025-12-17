"""
Database Factory Pattern Example Usage
=======================================

This module demonstrates how to use the database factory pattern to create
and interact with database clients using the wrapper pattern.

Architecture:
-------------
1. TenantsCollection (ABC) - Interface for tenants operations
2. MongoDBTenantsCollection - MongoDB implementation of TenantsCollection
3. BaseDatabaseClient (ABC) - Base interface with tenants() method
4. MongoDBDatabaseClient - MongoDB implementation of BaseDatabaseClient
5. DatabaseClient - Wrapper class that provides @property access to collections

Environment Variables Required:
-------------------------------
- DOCUMENT_DATABASE: "MONGO_DB" or "COSMOS_DB"
- MONGODB_CONNECTION_STRING: MongoDB connection string (if using MongoDB)
- MONGODB_DATABASE_NAME: Name of the database (optional, defaults to "aihub")

Example Usage:
-------------

# Option 1: Using environment variables
from aihub.database.client import get_database_client

# Get the DatabaseClient wrapper (singleton)
db_client = get_database_client()

# Access tenants collection via property
# db_client.tenants returns TenantsCollection interface
tenant = db_client.tenants.get("some-tenant-id")

# Get a list of tenants
tenants = db_client.tenants.get_list(filters={"name": "My Tenant"}, limit=10)

# Create a new tenant
from aihub.core.database.models.tenants import TenantModel

new_tenant = TenantModel(
    name="New Tenant",
    description="A new tenant for testing",
    meta={"key": "value"}
)
created_tenant = db_client.tenants.create(new_tenant)

# Update a tenant
updated_tenant = db_client.tenants.update(
    "tenant-id",
    {"description": "Updated description"}
)

# Delete a tenant
success = db_client.tenants.delete("tenant-id")

# Check database health
is_healthy = db_client.health_check()

# Close connection when done
db_client.disconnect()


# Option 2: Explicitly specify database type
from aihub.docdatabase.client import DatabaseClientFactory
from aihub.database.enums import DocumentDatabaseTypeEnum

db_client = DatabaseClientFactory.create(
    db_type=DocumentDatabaseTypeEnum.MONGO_DB,
    connection_string="mongodb://localhost:27017",
    database_name="aihub"
)

# Use the client as shown above
tenant = db_client.tenants.get("some-id")


# Pattern Benefits:
# -----------------
# 1. Single database connection (via singleton)
# 2. Clean interface separation (ABC for collections and clients)
# 3. Easy to extend with new collections
# 4. Type-safe with proper interface definitions
# 5. Database-agnostic API (MongoDB, Cosmos DB, etc.)
"""
