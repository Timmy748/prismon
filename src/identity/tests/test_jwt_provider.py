from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from identity.security.jwt import JwtTokenProvider


def test_should_encode_and_decode_token_successfully(
    jwt_provider: JwtTokenProvider,
):
    payload = {'sub': 'usr_123'}
    token = jwt_provider.generate_access_token(payload=payload)
    decoded_payload = jwt_provider.decode_access_token(token)

    assert decoded_payload['sub'] == payload['sub']


def test_should_generate_refresh_token_hash_with_correct_length(
    jwt_provider: JwtTokenProvider,
):
    refresh_token = 'raw_refresh_token_sample_123'
    hash_result = jwt_provider.generate_refresh_token_hash(refresh_token)
    expected_len = 64

    assert len(hash_result) == expected_len


def test_should_generate_refresh_token_hash_idempotently(
    jwt_provider: JwtTokenProvider,
):
    refresh_token = 'raw_refresh_token_sample_123'
    hash_result_1 = jwt_provider.generate_refresh_token_hash(refresh_token)
    hash_result_2 = jwt_provider.generate_refresh_token_hash(refresh_token)

    assert hash_result_1 == hash_result_2


def test_should_raise_error_when_token_is_expired(
    jwt_provider: JwtTokenProvider,
):
    payload = {'sub': 'usr_123'}
    with patch('identity.security.jwt.datetime') as mock_datetime:
        past_time = datetime.now(timezone.utc) - timedelta(minutes=30)
        mock_datetime.now.return_value = past_time
        token = jwt_provider.generate_access_token(payload=payload)

    with pytest.raises(ValueError, match='O token expirou.'):
        jwt_provider.decode_access_token(token)


def test_should_raise_error_when_token_is_invalid(
    jwt_provider: JwtTokenProvider,
):
    invalid_token = 'invalid.jwt.token.structure'

    with pytest.raises(ValueError, match='Token inválido.'):
        jwt_provider.decode_access_token(invalid_token)


def test_should_raise_error_when_signature_is_tampered_with(
    jwt_provider: JwtTokenProvider,
):
    payload = {'sub': 'usr_123'}
    token = jwt_provider.generate_access_token(payload=payload)
    tampered_token = token[:-5] + 'XXXXX'

    with pytest.raises(ValueError, match='Token inválido.'):
        jwt_provider.decode_access_token(tampered_token)


def test_should_raise_error_when_decoded_with_different_secret(
    jwt_provider: JwtTokenProvider,
):
    payload = {'sub': 'usr_123'}
    token = jwt_provider.generate_access_token(payload=payload)
    another_provider = JwtTokenProvider(
        secret_key='outra-chave-secreta-totalmente-diferente'
    )

    with pytest.raises(ValueError, match='Token inválido.'):
        another_provider.decode_access_token(token)
