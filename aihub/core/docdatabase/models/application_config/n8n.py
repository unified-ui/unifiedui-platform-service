from abc import ABC
from dataclasses import dataclass

from aihub.core.database.models.application_config.base import BaseApplicationConfig


@dataclass
class N8NAuthenticationConfig:
    type: str  # None, Basic, N8N User
    username: str | None = None
    password_hash: str | None = None


@dataclass
class N8NApplicationConfig(BaseApplicationConfig):
    type: str = "n8n"
    n8n_base_url: str
    authentication: N8NAuthenticationConfig
