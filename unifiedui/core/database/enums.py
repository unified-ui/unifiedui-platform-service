from enum import Enum


class TenantRolesEnum(str, Enum):
    READER = "READER"
    GLOBAL_ADMIN = "GLOBAL_ADMIN"
    CUSTOM_GROUPS_ADMIN = "CUSTOM_GROUPS_ADMIN"
    CUSTOM_GROUP_CREATOR = "CUSTOM_GROUP_CREATOR"
    APPLICATIONS_ADMIN = "APPLICATIONS_ADMIN"
    APPLICATIONS_CREATOR = "APPLICATIONS_CREATOR"
    CREDENTIALS_ADMIN = "CREDENTIALS_ADMIN"
    CREDENTIALS_CREATOR = "CREDENTIALS_CREATOR"
    CONVERSATIONS_ADMIN = "CONVERSATIONS_ADMIN"
    CONVERSATIONS_CREATOR = "CONVERSATIONS_CREATOR"
    AUTONOMOUS_AGENTS_ADMIN = "AUTONOMOUS_AGENTS_ADMIN"
    AUTONOMOUS_AGENTS_CREATOR = "AUTONOMOUS_AGENTS_CREATOR"
    CHAT_WIDGETS_ADMIN = "CHAT_WIDGETS_ADMIN"
    CHAT_WIDGETS_CREATOR = "CHAT_WIDGETS_CREATOR"
    REACT_AGENT_ADMIN = "REACT_AGENT_ADMIN"
    REACT_AGENT_CREATOR = "REACT_AGENT_CREATOR"
    TENANT_AI_MODELS_ADMIN = "TENANT_AI_MODELS_ADMIN"

    @classmethod
    def all(cls) -> list[str]:
        return [permission.value for permission in TenantRolesEnum]


class ToolTypeEnum(str, Enum):
    """Supported tool types for ReACT agents."""
    MCP_SERVER = "MCP_SERVER"
    OPENAPI_DEFINITION = "OPENAPI_DEFINITION"

    @classmethod
    def all(cls) -> list[str]:
        return [tool_type.value for tool_type in ToolTypeEnum]


class ApplicationTypeEnum(str, Enum):
    N8N = "N8N"
    MICROSOFT_FOUNDRY = "MICROSOFT_FOUNDRY"
    REST_API = "REST_API"

    @classmethod
    def all(cls) -> list[str]:
        return [app_type.value for app_type in ApplicationTypeEnum]


class AutonomousAgentTypeEnum(str, Enum):
    """Supported autonomous agent types."""
    N8N = "N8N"

    @classmethod
    def all(cls) -> list[str]:
        return [agent_type.value for agent_type in AutonomousAgentTypeEnum]


class ChatWidgetTypeEnum(str, Enum):
    IFRAME = "IFRAME"
    FORM = "FORM"

    @classmethod
    def all(cls) -> list[str]:
        return [widget_type.value for widget_type in ChatWidgetTypeEnum]


class PermissionActionEnum(str, Enum):
    READ = "READ"
    WRITE = "WRITE"
    ADMIN = "ADMIN"

    @classmethod
    def all(cls) -> list[str]:
        return [action.value for action in PermissionActionEnum]


class PrincipalTypeEnum(str, Enum):
    IDENTITY_USER = "IDENTITY_USER"
    IDENTITY_GROUP = "IDENTITY_GROUP"
    CUSTOM_GROUP = "CUSTOM_GROUP"

    @classmethod
    def all(cls) -> list[str]:
        return [principal_type.value for principal_type in PrincipalTypeEnum]


class UserPermissionEnum(str, Enum):
    """Special user-level permissions for resource access."""
    IS_CREATOR = "IS_CREATOR"

    @classmethod
    def all(cls) -> list[str]:
        return [perm.value for perm in UserPermissionEnum]


class OrderDirectionEnum(str, Enum):
    """Enum for sort order direction in list queries."""
    ASC = "asc"
    DESC = "desc"

    @classmethod
    def all(cls) -> list[str]:
        return [direction.value for direction in OrderDirectionEnum]


class ListViewEnum(str, Enum):
    """Enum for list view types."""
    FULL = "full"
    QUICK_LIST = "quick-list"

    @classmethod
    def all(cls) -> list[str]:
        return [view.value for view in ListViewEnum]


class AIModelTypeEnum(str, Enum):
    """Supported AI model types."""
    LLM_MODEL = "LLM_MODEL"
    EMBEDDING_MODEL = "EMBEDDING_MODEL"

    @classmethod
    def all(cls) -> list[str]:
        return [t.value for t in AIModelTypeEnum]


class AIModelProviderEnum(str, Enum):
    """Supported AI model providers."""
    AZURE_OPENAI = "AZURE_OPENAI"
    OPENAI = "OPENAI"
    ANTHROPIC = "ANTHROPIC"
    GOOGLE_GENAI = "GOOGLE_GENAI"
    OLLAMA = "OLLAMA"
    MISTRAL = "MISTRAL"
    GROQ = "GROQ"

    @classmethod
    def all(cls) -> list[str]:
        return [p.value for p in AIModelProviderEnum]


class AIModelPurposeGroupEnum(str, Enum):
    """Supported AI model purpose groups."""
    CONVERSATION_TITLE_GENERATION = "CONVERSATION_TITLE_GENERATION"
    CONVERSATION_SUMMARIZATION = "CONVERSATION_SUMMARIZATION"
    DESCRIPTION_GENERATION = "DESCRIPTION_GENERATION"
    TRACE_ANALYSIS = "TRACE_ANALYSIS"
    GENERAL = "GENERAL"
    REACT_AGENT = "REACT_AGENT"

    @classmethod
    def all(cls) -> list[str]:
        return [g.value for g in AIModelPurposeGroupEnum]


class NotificationTypeEnum(str, Enum):
    """Supported notification types."""
    AGENT_RUN_FAILED = "AGENT_RUN_FAILED"
    CREDENTIAL_EXPIRING = "CREDENTIAL_EXPIRING"
    TRACE_IMPORTED = "TRACE_IMPORTED"

    @classmethod
    def all(cls) -> list[str]:
        return [t.value for t in NotificationTypeEnum]
