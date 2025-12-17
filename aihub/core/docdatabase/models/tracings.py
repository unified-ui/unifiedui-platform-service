from aihub.core.database.models.base import BaseDatabaseModel


class TracingModel(BaseDatabaseModel):
    name: str
    description: str | None = None
    meta: dict | None = None
