from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class RefreshTokenDTO:
    id: int
    user_id: int
    token_hash: str
    expires_at: datetime
    revoked: bool


@dataclass(frozen=True, slots=True)
class CreateRefreshTokenDTO:
    user_id: int
    token_hash: str
    expires_at: datetime
