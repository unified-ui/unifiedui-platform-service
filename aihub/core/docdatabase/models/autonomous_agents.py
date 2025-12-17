from aihub.core.database.models.base import BaseDatabaseModel


class AutonomousAgentModel(BaseDatabaseModel):
    name: str
    config: dict
    description: str | None = None
