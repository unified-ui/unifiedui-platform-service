from enum import Enum


class DocumentDatabaseTypeEnum(str, Enum):
    MONGO_DB = "MONGO_DB"
    COSMOS_DB = "COSMOS_DB"
