from pydantic import BaseModel, Field
from uuid import uuid4

from aihub.utils.default_factory_functions import current_iso_datetime


class BaseDatabaseModel(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    created_at: str = Field(default_factory=current_iso_datetime)
    updated_at: str = Field(default_factory=current_iso_datetime)
