from pydantic import BaseModel


class KeyStoreSecretMetadataModel(BaseModel):
    name: str
    description: str | None = None
    meta: dict | None = None
