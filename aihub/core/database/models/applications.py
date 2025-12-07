from aihub.core.database.models.base import BaseDatabaseModel


class ApplicationModel(BaseDatabaseModel):
    name: str
    version: str
    description: str | None = None
    config: dict
