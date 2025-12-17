from aihub.core.database.models.base import BaseDatabaseModel


class CredentialModel(BaseDatabaseModel):
    name: str
    type: str
    uri: str
    meta: dict | None = None
