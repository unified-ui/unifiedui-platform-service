from abc import ABC, abstractmethod

from aihub.core.database.models.base import BaseDatabaseModel
from aihub.core.database.models.application_config.base import BaseApplicationConfig


class ApplicationModel(BaseDatabaseModel):
    name: str
    version: str
    description: str | None = None
    config: BaseApplicationConfig
