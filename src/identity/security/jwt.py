import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Protocol

import jwt

from identity.settings import get_settings


class ITokenProvider(Protocol):
    def generate_access_token(self, payload: Dict[str, Any]) -> str: ...

    def decode_access_token(self, token: str) -> Dict[str, Any]: ...

    def generate_refresh_token_hash(self, refresh_token_raw: str) -> str: ...


class JwtTokenProvider(ITokenProvider):
    def __init__(
        self,
        secret_key: str,
        algorithm: str = 'HS256',
        expires_in_minutes: int = 15,
    ):
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._expires_in_minutes = expires_in_minutes

    def generate_access_token(self, payload: Dict[str, Any]) -> str:
        data_to_encode = payload.copy()
        now = datetime.now(timezone.utc)

        data_to_encode.update(
            {
                'exp': now + timedelta(minutes=self._expires_in_minutes),
                'iat': now,
            }
        )

        token = jwt.encode(
            data_to_encode, self._secret_key, algorithm=self._algorithm
        )
        return token

    def decode_access_token(self, token: str) -> Dict[str, Any]:
        try:
            decoded = jwt.decode(
                token, self._secret_key, algorithms=[self._algorithm]
            )
            return decoded
        except jwt.ExpiredSignatureError:
            raise ValueError('O token expirou.')
        except jwt.InvalidTokenError:
            raise ValueError('Token inválido.')

    def generate_refresh_token_hash(self, refresh_token_raw: str) -> str:
        return hashlib.sha256(refresh_token_raw.encode('utf-8')).hexdigest()


def create_token_provider() -> ITokenProvider:
    settings = get_settings()
    return JwtTokenProvider(
        secret_key=settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
        expires_in_minutes=settings.jwt_expires_in_minutes,
    )
