from typing import Optional, List
from pymongo.database import Database
from pymongo.collection import Collection

from unifiedui.core.docdatabase.collections.tenants import TenantsCollection
from unifiedui.core.docdatabase.models.tenants import TenantModel
from unifiedui.utils.default_factory_functions import current_iso_datetime


class MongoDBTenantsCollection(TenantsCollection):
    """MongoDB implementation for Tenants collection."""

    def __init__(self, db: Database):
        self._db = db
        self._collection: Collection = db["tenants"]

    def get(self, id: str) -> Optional[TenantModel]:
        """Get a single tenant by ID."""
        doc = self._collection.find_one({"id": id})
        if doc:
            # Remove MongoDB's _id field
            doc.pop("_id", None)
            return TenantModel(**doc)
        return None

    def get_list(
        self,
        filters: Optional[dict] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[TenantModel]:
        """Get a list of tenants with optional filters."""
        filters = filters or {}
        cursor = self._collection.find(filters).skip(skip).limit(limit)
        
        tenants = []
        for doc in cursor:
            doc.pop("_id", None)
            tenants.append(TenantModel(**doc))
        
        return tenants

    def create(self, data: TenantModel) -> TenantModel:
        """Create a new tenant."""
        doc = data.model_dump()
        self._collection.insert_one(doc)
        return data

    def update(self, id: str, data: dict) -> Optional[TenantModel]:
        """Update an existing tenant."""
        # Update the updated_at timestamp
        data["updated_at"] = current_iso_datetime()
        
        result = self._collection.find_one_and_update(
            {"id": id},
            {"$set": data},
            return_document=True
        )
        
        if result:
            result.pop("_id", None)
            return TenantModel(**result)
        return None

    def delete(self, id: str) -> bool:
        """Delete a tenant by ID."""
        result = self._collection.delete_one({"id": id})
        return result.deleted_count > 0
