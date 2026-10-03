import pytest

from identity.security.jwt import JwtTokenProvider
from identity.security.password_hasher import Argonid2Hasher


@pytest.fixture
def argon2_hasher() -> Argonid2Hasher:
    return Argonid2Hasher(pepper='pepper')


@pytest.fixture
def jwt_provider() -> JwtTokenProvider:
    return JwtTokenProvider(
        secret_key='minha-chave-secreta-de-teste',
        algorithm='HS256',
        expires_in_minutes=15,
    )
