from dataclasses import dataclass, field
from datetime import datetime

from project.entities.api_key import ApiKeyProvider


@dataclass(frozen=True)
class CreateApiKeyDTO:
    provider: ApiKeyProvider
    api_hint: str
    encrypted_api_key: bytes = field(repr=False)
    encrypted_dek: bytes = field(repr=False)
    api_key_nonce: bytes = field(repr=False)
    dek_nonce: bytes = field(repr=False)
    member_id: int | None = None
    project_id: int | None = None


@dataclass(frozen=True)
class ApiKeyDTO:
    id: int
    provider: ApiKeyProvider
    api_hint: str
    encrypted_api_key: bytes = field(repr=False)
    encrypted_dek: bytes = field(repr=False)
    api_key_nonce: bytes = field(repr=False)
    dek_nonce: bytes = field(repr=False)
    member_id: int | None
    project_id: int | None
    created_at: datetime
