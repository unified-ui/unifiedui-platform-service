from enum import StrEnum


class TenantRolesEnum(StrEnum):
    READER = "READER"
    TENANT_GLOBAL_ADMIN = "TENANT_GLOBAL_ADMIN"
    CUSTOM_GROUPS_ADMIN = "CUSTOM_GROUPS_ADMIN"
    CUSTOM_GROUP_CREATOR = "CUSTOM_GROUP_CREATOR"
    CHAT_AGENTS_ADMIN = "CHAT_AGENTS_ADMIN"
    CHAT_AGENTS_CREATOR = "CHAT_AGENTS_CREATOR"
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
    EXTERNAL_APPS_ADMIN = "EXTERNAL_APPS_ADMIN"
    EXTERNAL_APPS_CREATOR = "EXTERNAL_APPS_CREATOR"

    @classmethod
    def all(cls) -> list[str]:
        return [permission.value for permission in TenantRolesEnum]


class ToolTypeEnum(StrEnum):
    """Supported tool types for ReACT agents."""

    MCP_SERVER = "MCP_SERVER"
    OPENAPI_DEFINITION = "OPENAPI_DEFINITION"

    @classmethod
    def all(cls) -> list[str]:
        return [tool_type.value for tool_type in ToolTypeEnum]


class ChatAgentTypeEnum(StrEnum):
    N8N = "N8N"
    MICROSOFT_FOUNDRY = "MICROSOFT_FOUNDRY"
    REST_API = "REST_API"
    REACT_AGENT = "REACT_AGENT"

    @classmethod
    def all(cls) -> list[str]:
        return [agent_type.value for agent_type in ChatAgentTypeEnum]


class RestApiAuthTypeEnum(StrEnum):
    """Supported authentication types for REST API agents."""

    ANONYMOUS = "ANONYMOUS"
    BASIC_AUTH = "BASIC_AUTH"
    API_KEY = "API_KEY"
    ENTRA_ID_USER_TOKEN = "ENTRA_ID_USER_TOKEN"
    ENTRA_ID_APP_REGISTRATION = "ENTRA_ID_APP_REGISTRATION"

    @classmethod
    def all(cls) -> list[str]:
        return [auth_type.value for auth_type in RestApiAuthTypeEnum]


class AutonomousAgentTypeEnum(StrEnum):
    """Supported autonomous agent types."""

    N8N = "N8N"

    @classmethod
    def all(cls) -> list[str]:
        return [agent_type.value for agent_type in AutonomousAgentTypeEnum]


class ChatWidgetTypeEnum(StrEnum):
    IFRAME = "IFRAME"
    FORM = "FORM"

    @classmethod
    def all(cls) -> list[str]:
        return [widget_type.value for widget_type in ChatWidgetTypeEnum]


class PermissionActionEnum(StrEnum):
    READ = "READ"
    WRITE = "WRITE"
    ADMIN = "ADMIN"

    @classmethod
    def all(cls) -> list[str]:
        return [action.value for action in PermissionActionEnum]


class PrincipalTypeEnum(StrEnum):
    IDENTITY_USER = "IDENTITY_USER"
    IDENTITY_GROUP = "IDENTITY_GROUP"
    CUSTOM_GROUP = "CUSTOM_GROUP"

    @classmethod
    def all(cls) -> list[str]:
        return [principal_type.value for principal_type in PrincipalTypeEnum]


class UserPermissionEnum(StrEnum):
    """Special user-level permissions for resource access."""

    IS_CREATOR = "IS_CREATOR"

    @classmethod
    def all(cls) -> list[str]:
        return [perm.value for perm in UserPermissionEnum]


class OrderDirectionEnum(StrEnum):
    """Enum for sort order direction in list queries."""

    ASC = "asc"
    DESC = "desc"

    @classmethod
    def all(cls) -> list[str]:
        return [direction.value for direction in OrderDirectionEnum]


class ListViewEnum(StrEnum):
    """Enum for list view types."""

    FULL = "full"
    QUICK_LIST = "quick-list"

    @classmethod
    def all(cls) -> list[str]:
        return [view.value for view in ListViewEnum]


class AIModelTypeEnum(StrEnum):
    """Supported AI model types."""

    LLM_MODEL = "LLM_MODEL"
    EMBEDDING_MODEL = "EMBEDDING_MODEL"

    @classmethod
    def all(cls) -> list[str]:
        return [t.value for t in AIModelTypeEnum]


class AIModelProviderEnum(StrEnum):
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


class OrganizationRoleEnum(StrEnum):
    """Organization-level roles."""

    ORGANISATION_GLOBAL_ADMIN = "ORGANISATION_GLOBAL_ADMIN"
    ORGANISATION_TENANT_ADMIN = "ORGANISATION_TENANT_ADMIN"
    ORGANISATION_TENANT_CREATOR = "ORGANISATION_TENANT_CREATOR"

    @classmethod
    def all(cls) -> list[str]:
        return [role.value for role in OrganizationRoleEnum]


class EnvironmentTypeEnum(StrEnum):
    """Tenant environment types."""

    SANDBOX = "SANDBOX"
    PRODUCTION = "PRODUCTION"

    @classmethod
    def all(cls) -> list[str]:
        return [env.value for env in EnvironmentTypeEnum]


class AIModelPurposeGroupEnum(StrEnum):
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


class FileContextTypeEnum(StrEnum):
    """Context types for uploaded files."""

    CHAT_ATTACHMENT = "CHAT_ATTACHMENT"
    APP_IMAGE = "APP_IMAGE"

    @classmethod
    def all(cls) -> list[str]:
        return [t.value for t in FileContextTypeEnum]
