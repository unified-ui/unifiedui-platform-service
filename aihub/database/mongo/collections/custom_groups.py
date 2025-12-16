"""MongoDB implementation for custom groups collection."""
from typing import Optional
from datetime import datetime, timezone
from pymongo.collection import Collection

from aihub.core.database.collections.custom_groups import CustomGroupsCollection
from aihub.core.database.models.custom_groups import CustomGroupModel
from aihub.utils.default_factory_functions import generate_id
from aihub.logger import get_logger

logger = get_logger(__name__)


class MongoDBCustomGroupsCollection(CustomGroupsCollection):
    """MongoDB implementation of CustomGroupsCollection."""

    def __init__(self, collection: Collection):
        self._collection = collection
        logger.info("MongoDB custom groups collection initialized")

    def get(self, group_id: str) -> Optional[CustomGroupModel]:
        """Get a custom group by ID."""
        doc = self._collection.find_one({"id": group_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return CustomGroupModel(**doc)

    def get_list(
        self,
        filters: Optional[dict] = None,
        skip: int = 0,
        limit: int = 100
    ) -> list[CustomGroupModel]:
        """List custom groups with optional filtering."""
        query = filters or {}
        docs = self._collection.find(query).skip(skip).limit(limit)
        
        groups = []
        for doc in docs:
            doc.pop("_id", None)
            groups.append(CustomGroupModel(**doc))
        
        return groups

    def create(
        self,
        tenant_id: str,
        name: str,
        description: Optional[str],
        member_ids: list[str],
        created_by: str
    ) -> CustomGroupModel:
        """Create a new custom group."""
        now = datetime.now(timezone.utc)
        
        group = CustomGroupModel(
            id=generate_id(),
            tenant_id=tenant_id,
            name=name,
            description=description,
            member_ids=member_ids or [],
            created_at=now,
            updated_at=now,
            created_by=created_by,
            updated_by=created_by
        )
        
        doc = group.model_dump()
        self._collection.insert_one(doc)
        
        logger.info(f"Created custom group {group.id} for tenant {tenant_id}")
        return group

    def update(
        self,
        group_id: str,
        name: Optional[str],
        description: Optional[str],
        updated_by: str
    ) -> Optional[CustomGroupModel]:
        """Update an existing custom group."""
        update_fields = {
            "updated_at": datetime.now(timezone.utc),
            "updated_by": updated_by
        }
        
        if name is not None:
            update_fields["name"] = name
        if description is not None:
            update_fields["description"] = description
        
        result = self._collection.find_one_and_update(
            {"id": group_id},
            {"$set": update_fields},
            return_document=True
        )
        
        if not result:
            return None
        
        result.pop("_id", None)
        logger.info(f"Updated custom group {group_id}")
        return CustomGroupModel(**result)

    def add_members(
        self,
        group_id: str,
        user_ids: list[str],
        updated_by: str
    ) -> Optional[CustomGroupModel]:
        """Add members to a custom group."""
        result = self._collection.find_one_and_update(
            {"id": group_id},
            {
                "$addToSet": {"member_ids": {"$each": user_ids}},
                "$set": {
                    "updated_at": datetime.now(timezone.utc),
                    "updated_by": updated_by
                }
            },
            return_document=True
        )
        
        if not result:
            return None
        
        result.pop("_id", None)
        logger.info(f"Added {len(user_ids)} members to custom group {group_id}")
        return CustomGroupModel(**result)

    def remove_members(
        self,
        group_id: str,
        user_ids: list[str],
        updated_by: str
    ) -> Optional[CustomGroupModel]:
        """Remove members from a custom group."""
        result = self._collection.find_one_and_update(
            {"id": group_id},
            {
                "$pullAll": {"member_ids": user_ids},
                "$set": {
                    "updated_at": datetime.now(timezone.utc),
                    "updated_by": updated_by
                }
            },
            return_document=True
        )
        
        if not result:
            return None
        
        result.pop("_id", None)
        logger.info(f"Removed {len(user_ids)} members from custom group {group_id}")
        return CustomGroupModel(**result)

    def delete(self, group_id: str) -> bool:
        """Delete a custom group."""
        result = self._collection.delete_one({"id": group_id})
        
        if result.deleted_count > 0:
            logger.info(f"Deleted custom group {group_id}")
            return True
        
        return False
