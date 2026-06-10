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
    WORKFLOWS_ADMIN = "WORKFLOWS_ADMIN"
    WORKFLOWS_CREATOR = "WORKFLOWS_CREATOR"
    CHAT_WIDGETS_ADMIN = "CHAT_WIDGETS_ADMIN"
    CHAT_WIDGETS_CREATOR = "CHAT_WIDGETS_CREATOR"
    TENANT_AI_MODELS_ADMIN = "TENANT_AI_MODELS_ADMIN"
    EXTERNAL_APPS_ADMIN = "EXTERNAL_APPS_ADMIN"
    EXTERNAL_APPS_CREATOR = "EXTERNAL_APPS_CREATOR"

    @classmethod
    def all(cls) -> list[str]:
        return [permission.value for permission in TenantRolesEnum]


class ChatAgentTypeEnum(StrEnum):
    N8N = "N8N"
    MICROSOFT_FOUNDRY = "MICROSOFT_FOUNDRY"
    REST_API = "REST_API"
    LLM = "LLM"

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


class MicrosoftFoundryAuthTypeEnum(StrEnum):
    """Supported authentication types for Microsoft Foundry chat agents."""

    ENTRA_ID_USER_TOKEN = "ENTRA_ID_USER_TOKEN"
    ENTRA_ID_APP_REGISTRATION = "ENTRA_ID_APP_REGISTRATION"
    API_KEY = "API_KEY"
    CUSTOM_REST_API = "CUSTOM_REST_API"

    @classmethod
    def all(cls) -> list[str]:
        return [auth_type.value for auth_type in MicrosoftFoundryAuthTypeEnum]


class MicrosoftFoundryCustomRestApiAuthTypeEnum(StrEnum):
    """Supported authentication types for Custom REST API proxy in Foundry mode."""

    API_KEY = "API_KEY"
    USER_TOKEN = "USER_TOKEN"
    ENTRA_ID_APP_REGISTRATION = "ENTRA_ID_APP_REGISTRATION"

    @classmethod
    def all(cls) -> list[str]:
        return [auth_type.value for auth_type in MicrosoftFoundryCustomRestApiAuthTypeEnum]


class WorkflowTypeEnum(StrEnum):
    """Supported workflow types."""

    N8N = "N8N"

    @classmethod
    def all(cls) -> list[str]:
        return [workflow_type.value for workflow_type in WorkflowTypeEnum]


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
    GENERAL = "GENERAL"
    DIRECT_CHAT = "DIRECT_CHAT"

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


class MessageFeedbackRatingEnum(StrEnum):
    """Rating value for message feedback."""

    THUMBS_UP = "THUMBS_UP"
    THUMBS_DOWN = "THUMBS_DOWN"

    @classmethod
    def all(cls) -> list[str]:
        return [t.value for t in MessageFeedbackRatingEnum]


class MessageFeedbackReasonEnum(StrEnum):
    """Structured reasons for message feedback."""

    HALLUCINATION = "HALLUCINATION"
    TOO_SLOW = "TOO_SLOW"
    FORMATTING = "FORMATTING"
    INACCURATE = "INACCURATE"
    INAPPROPRIATE = "INAPPROPRIATE"
    INCOMPLETE = "INCOMPLETE"
    OTHER = "OTHER"

    @classmethod
    def all(cls) -> list[str]:
        return [t.value for t in MessageFeedbackReasonEnum]
