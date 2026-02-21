from dataclasses import dataclass

from unifiedui.core.database.chat_agent_config.base import BaseChatAgentConfig


@dataclass
class N8NAuthenticationConfig:
    type: str  # None, Basic, N8N User
    username: str | None = None
    password_hash: str | None = None


@dataclass
class N8NChatAgentConfig(BaseChatAgentConfig):
    type: str = "n8n"
    n8n_base_url: str
    authentication: N8NAuthenticationConfig
