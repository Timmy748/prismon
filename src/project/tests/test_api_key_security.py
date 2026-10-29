import base64
from dataclasses import replace
from types import SimpleNamespace

import pytest
from cryptography.exceptions import InvalidTag
from pydantic import SecretStr

from project.security import api_key
from project.security.api_key import ApiKeyEncryption


def test_encrypt_decrypt_restores_unicode_key(key_encryptor):
    encrypted = key_encryptor.encrypt('secret-🔑')
    assert key_encryptor.decrypt(encrypted) == 'secret-🔑'


@pytest.mark.parametrize('value', ['!', base64.b64encode(b'short').decode()])
def test_invalid_kek_is_rejected(value):
    with pytest.raises(ValueError, match='API_KEY_KEK'):
        ApiKeyEncryption(value)


def test_encryption_uses_fresh_keys_and_nonces(key_encryptor):
    first = key_encryptor.encrypt('same-key')
    second = key_encryptor.encrypt('same-key')
    assert first != second


@pytest.mark.parametrize('field', ['encrypted_api_key', 'encrypted_dek'])
def test_modified_ciphertext_is_rejected(key_encryptor, field):
    encrypted = key_encryptor.encrypt('secret')
    altered = replace(
        encrypted,
        **{
            field: bytes([getattr(encrypted, field)[0] ^ 1])
            + getattr(encrypted, field)[1:]
        },
    )
    with pytest.raises(InvalidTag):
        key_encryptor.decrypt(altered)


def test_wrong_kek_is_rejected(key_encryptor):
    encrypted = key_encryptor.encrypt('secret')
    other = ApiKeyEncryption(base64.b64encode(b'x' * 32).decode())
    with pytest.raises(InvalidTag):
        other.decrypt(encrypted)


def test_encryption_factory_uses_configured_kek(monkeypatch):
    kek = base64.b64encode(b'k' * 32).decode()
    monkeypatch.setattr(
        api_key,
        'get_settings',
        lambda: SimpleNamespace(API_KEY_KEK=SecretStr(kek)),
    )
    encryptor = api_key.create_api_key_encryption()
    assert encryptor.decrypt(encryptor.encrypt('secret')) == 'secret'
