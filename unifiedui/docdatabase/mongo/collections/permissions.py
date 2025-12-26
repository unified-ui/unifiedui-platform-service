"""MongoDB implementation for Permissions collection."""
from typing import Optional, List
from pymongo.database import Database
from pymongo.collection import Collection

from unifiedui.core.docdatabase.collections.permissions import PermissionsCollection
from unifiedui.core.docdatabase.models.permissions import PermissionModel, AssignedTo


class MongoDBPermissionsCollection(PermissionsCollection):
    """MongoDB implementation for Permissions collection."""

    def __init__(self, db: Database):
        self._db = db
        self._collection: Collection = db["permissions"]
        self._ensure_indexes()

    def _ensure_indexes(self):
        """Create necessary indexes for performance."""
        # Index for resource-based queries
        self._collection.create_index([
            ("tenant_id", 1),
            ("resource_type", 1),
            ("resource_id", 1)
        ])
        
        # Index for user permission lookups
        self._collection.create_index([
            ("tenant_id", 1),
            ("assigned_to.type", 1),
            ("assigned_to.id", 1)
        ])
        
        # Compound index for permission checks
        self._collection.create_index([
            ("tenant_id", 1),
            ("resource_type", 1),
            ("resource_id", 1),
            ("action", 1)
        ])

    def get(self, id: str) -> Optional[PermissionModel]:
        """Get a single permission by ID."""
        doc = self._collection.find_one({"id": id})
        if doc:
            doc.pop("_id", None)
            return PermissionModel(**doc)
        return None

    def get_list(
        self,
        filters: Optional[dict] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[PermissionModel]:
        """Get a list of permissions with optional filters."""
        filters = filters or {}
        cursor = self._collection.find(filters).skip(skip).limit(limit)
        
        permissions = []
        for doc in cursor:
            doc.pop("_id", None)
            permissions.append(PermissionModel(**doc))
        
        return permissions

    def get_resource_permissions(
        self,
        resource_type: str,
        resource_id: str,
        tenant_id: str
    ) -> List[PermissionModel]:
        """Get all permissions for a specific resource."""
        cursor = self._collection.find({
            "tenant_id": tenant_id,
            "resource_type": resource_type,
            "resource_id": resource_id
        })
        
        permissions = []
        for doc in cursor:
            doc.pop("_id", None)
            permissions.append(PermissionModel(**doc))
        
        return permissions

    def get_user_accessible_resources(
        self,
        resource_type: str,
        tenant_id: str,
        assigned_to_list: List[AssignedTo],
        action: Optional[str] = None
    ) -> List[str]:
        """
        Get list of resource IDs that a user (or their groups) can access.
        
        This is the critical method for list filtering!
        """
        # Build $or query for assigned_to matching
        # MongoDB doesn't support $in with nested objects properly
        or_conditions = []
        for at in assigned_to_list:
            or_conditions.append({
                "assigned_to.type": at.type,
                "assigned_to.id": at.id
            })
        
        query = {
            "tenant_id": tenant_id,
            "resource_type": resource_type,
            "$or": or_conditions
        }
        
        # Optional: Filter by specific action
        if action:
            query["action"] = action
        
        # Get distinct resource IDs
        resource_ids = self._collection.distinct("resource_id", query)
        return resource_ids

    def check_permission(
        self,
        resource_type: str,
        resource_id: str,
        tenant_id: str,
        assigned_to_list: List[AssignedTo],
        action: str
    ) -> bool:
        """Check if user has specific permission on a resource."""
        # Build $or query for assigned_to matching
        or_conditions = []
        for at in assigned_to_list:
            or_conditions.append({
                "assigned_to.type": at.type,
                "assigned_to.id": at.id
            })
        
        result = self._collection.find_one({
            "tenant_id": tenant_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "action": action,
            "$or": or_conditions
        })
        
        return result is not None

    def create(self, data: PermissionModel) -> PermissionModel:
        """Create a new permission."""
        doc = data.model_dump()
        self._collection.insert_one(doc)
        return data

    def create_many(self, permissions: List[PermissionModel]) -> List[PermissionModel]:
        """Create multiple permissions at once."""
        if not permissions:
            return []
        
        docs = [perm.model_dump() for perm in permissions]
        self._collection.insert_many(docs)
        return permissions

    def delete(self, id: str) -> bool:
        """Delete a permission by ID."""
        result = self._collection.delete_one({"id": id})
        return result.deleted_count > 0

    def delete_resource_permissions(
        self,
        resource_type: str,
        resource_id: str,
        tenant_id: str,
        assigned_to: Optional[AssignedTo] = None
    ) -> int:
        """Delete permissions for a resource, optionally filtered by assigned_to."""
        query = {
            "tenant_id": tenant_id,
            "resource_type": resource_type,
            "resource_id": resource_id
        }
        
        if assigned_to:
            # Use field-level matching for nested object (MongoDB doesn't match nested objects correctly)
            query["assigned_to.type"] = assigned_to.type
            query["assigned_to.id"] = assigned_to.id
        
        result = self._collection.delete_many(query)
        return result.deleted_count
