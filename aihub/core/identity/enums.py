from enum import Enum


class IdenityProviderEnum(str, Enum):
    MOCK = "MOCK"
    EXTRA_ID = "EXTRA_ID"
    AWS_COGNITO = "AWS_COGNITO"
    GOOGLE_IDENTITY = "GOOGLE_IDENTITY"
