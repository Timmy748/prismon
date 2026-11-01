import base64
import binascii
import os
from dataclasses import dataclass
from typing import Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from infra.logs import get_logger
from infra.settings import get_settings

logger = get_logger(__name__)

_NONCE_SIZE = 12
_KEY_SIZE = 32
_API_KEY_AAD = b'prismon:api-key:v1'
_DEK_AAD = b'prismon:api-key-dek:v1'


@dataclass(frozen=True, repr=False)
class EncryptedApiKey:
    encrypted_api_key: bytes
    encrypted_dek: bytes
    api_key_nonce: bytes
    dek_nonce: bytes


class IApiKeyEncryption(Protocol):
    def encrypt(self, secret: str) -> EncryptedApiKey: ...

    def decrypt(self, encrypted: EncryptedApiKey) -> str: ...


class ApiKeyEncryption:
    def __init__(self, kek: str) -> None:
        try:
            key = base64.b64decode(kek, validate=True)
        except (ValueError, binascii.Error) as error:
            raise ValueError('API_KEY_KEK must be base64 encoded') from error
        if len(key) != _KEY_SIZE:
            raise ValueError('API_KEY_KEK must encode exactly 32 bytes')
        self._kek = key

    def encrypt(self, secret: str) -> EncryptedApiKey:
        logger.debug('API key encryption started')
        dek = AESGCM.generate_key(bit_length=256)
        api_key_nonce = os.urandom(_NONCE_SIZE)
        dek_nonce = os.urandom(_NONCE_SIZE)
        encrypted = EncryptedApiKey(
            encrypted_api_key=AESGCM(dek).encrypt(
                api_key_nonce, secret.encode('utf-8'), _API_KEY_AAD
            ),
            encrypted_dek=AESGCM(self._kek).encrypt(dek_nonce, dek, _DEK_AAD),
            api_key_nonce=api_key_nonce,
            dek_nonce=dek_nonce,
        )
        logger.debug('API key encryption completed')
        return encrypted

    def decrypt(self, encrypted: EncryptedApiKey) -> str:
        logger.debug('API key decryption started')
        dek = AESGCM(self._kek).decrypt(
            encrypted.dek_nonce, encrypted.encrypted_dek, _DEK_AAD
        )
        plaintext = AESGCM(dek).decrypt(
            encrypted.api_key_nonce, encrypted.encrypted_api_key, _API_KEY_AAD
        )
        secret = plaintext.decode('utf-8')
        logger.debug('API key decryption completed')
        return secret


def create_api_key_encryption() -> IApiKeyEncryption:
    encryptor = ApiKeyEncryption(get_settings().API_KEY_KEK.get_secret_value())
    logger.debug('API key encryption service initialized')
    return encryptor
