from aihub.core.database.models.base import BaseDatabaseModel


class CustomGroupModel(BaseDatabaseModel):
    name: str
    description: str | None = None
    meta: dict | None = None
