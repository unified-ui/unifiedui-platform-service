from enum import Enum


class TenantPermissionEnum(str, Enum):
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

    def all() -> list[str]:
        return [permission.value for permission in TenantPermissionEnum]


class PermissionActionEnum(str, Enum):
    READ = "READ"
    WRITE = "WRITE"
    ADMIN = "ADMIN"

    def all() -> list[str]:
        return [action.value for action in PermissionActionEnum]


class PrincipalTypeEnum(str, Enum):
    IDENTITY_USER = "IDENTITY_USER"
    IDENTITY_GROUP = "IDENTITY_GROUP"
    CUSTOM_GROUP = "CUSTOM_GROUP"

    def all() -> list[str]:
        return [principal_type.value for principal_type in PrincipalTypeEnum]
