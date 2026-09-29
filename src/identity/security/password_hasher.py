import hmac
from hashlib import sha256
from typing import Protocol

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from identity.settings import get_settings


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, plain_password: str, hashed_password: str) -> bool: ...


class Argonid2Hasher(PasswordHasher):
    def __init__(self, pepper: str) -> None:
        self._pepper: bytes = pepper.encode('utf-8')

        self._ph: PasswordHash = PasswordHash((Argon2Hasher(),))

    def _hmac(self, password: str) -> str:
        return hmac.new(
            self._pepper, password.encode('utf-8'), sha256
        ).hexdigest()

    def hash(self, password: str) -> str:
        hmac_password = self._hmac(password)
        return self._ph.hash(hmac_password)

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        hmac_password = self._hmac(plain_password)
        return self._ph.verify(hmac_password, hashed_password)


def create_password_hasher() -> PasswordHasher:  # pragma: no cover
    return Argonid2Hasher(
        pepper=get_settings().password_pepper.get_secret_value()
    )
