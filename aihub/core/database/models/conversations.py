from aihub.core.database.models.base import BaseDatabaseModel


class ConversationModel(BaseDatabaseModel):
    application_id: str
    title: str
    description: str | None = None
    meta: dict | None = None


class ConverstionMessageModel(BaseDatabaseModel):
    conversation_id: str
    role: str
    content: str
    meta: dict | None = None
