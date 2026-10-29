from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from project.entities.api_key import ApiKeyProvider


class CreateApiKeySchema(BaseModel):
    provider: ApiKeyProvider
    api_key: SecretStr = Field(min_length=1)


class ApiKeyHintSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: ApiKeyProvider
    api_hint: str
    created_at: datetime
