# ruff: noqa: PLR0913, PLR0917
from project.dtos.api_key import ApiKeyDTO, CreateApiKeyDTO
from project.dtos.api_key_hint import ApiKeyHintDTO
from project.dtos.page import CursorPage, PaginationDTO
from project.entities.api_key import ApiKeyProvider
from project.exceptions import (
    ApiKeyNotFoundException,
    InsufficientProjectPermissionException,
)
from project.security.api_key import EncryptedApiKey, IApiKeyEncryption
from project.unit_of_work import IProjectUnitOfWork
from project.use_cases.project import _require_project_member

_HINT_LENGTH = 4


def _hint(key: ApiKeyDTO) -> ApiKeyHintDTO:
    return ApiKeyHintDTO(
        id=key.id,
        provider=key.provider,
        api_hint=key.api_hint,
        created_at=key.created_at,
    )


async def _create(
    uow: IProjectUnitOfWork,
    provider: ApiKeyProvider,
    api_key: str,
    encryptor: IApiKeyEncryption,
    *,
    member_id: int | None = None,
    project_id: int | None = None,
) -> ApiKeyHintDTO:
    encrypted = encryptor.encrypt(api_key)
    key = await uow.api_key_repository.create_api_key(
        CreateApiKeyDTO(
            provider=provider,
            api_hint=(
                f'****{api_key[-_HINT_LENGTH:]}'
                if len(api_key) > _HINT_LENGTH
                else '****'
            ),
            encrypted_api_key=encrypted.encrypted_api_key,
            encrypted_dek=encrypted.encrypted_dek,
            api_key_nonce=encrypted.api_key_nonce,
            dek_nonce=encrypted.dek_nonce,
            member_id=member_id,
            project_id=project_id,
        )
    )
    await uow.commit()
    return _hint(key)


async def create_member_api_key(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    provider: ApiKeyProvider,
    api_key: str,
    encryptor: IApiKeyEncryption,
) -> ApiKeyHintDTO:
    _, member = await _require_project_member(uow, project_id, user_id)
    return await _create(uow, provider, api_key, encryptor, member_id=member.id)


async def create_project_api_key(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    provider: ApiKeyProvider,
    api_key: str,
    encryptor: IApiKeyEncryption,
) -> ApiKeyHintDTO:
    project, _ = await _require_project_member(uow, project_id, user_id)
    if project.owner_id != user_id:
        raise InsufficientProjectPermissionException('api_key:create')
    return await _create(
        uow, provider, api_key, encryptor, project_id=project_id
    )


async def list_member_api_keys(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    pagination: PaginationDTO = PaginationDTO(),
) -> CursorPage[ApiKeyHintDTO]:
    _, member = await _require_project_member(uow, project_id, user_id)
    page = await uow.api_key_repository.list_member_api_keys(
        member.id, pagination
    )
    return CursorPage(
        items=[_hint(key) for key in page.items], pagination=page.pagination
    )


async def list_project_api_keys(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    pagination: PaginationDTO = PaginationDTO(),
) -> CursorPage[ApiKeyHintDTO]:
    await _require_project_member(uow, project_id, user_id)
    page = await uow.api_key_repository.list_project_api_keys(
        project_id, pagination
    )
    return CursorPage(
        items=[_hint(key) for key in page.items], pagination=page.pagination
    )


async def get_api_key(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    api_key_id: int,
    encryptor: IApiKeyEncryption,
) -> str:
    _, member = await _require_project_member(uow, project_id, user_id)
    key = await uow.api_key_repository.get_api_key(api_key_id)
    if key is None:
        raise ApiKeyNotFoundException(api_key_id)
    owns_key = (
        key.member_id == member.id and key.project_id is None
        if key.member_id is not None
        else key.project_id == project_id
    )
    if not owns_key:
        raise ApiKeyNotFoundException(api_key_id)

    return encryptor.decrypt(
        EncryptedApiKey(
            encrypted_api_key=key.encrypted_api_key,
            encrypted_dek=key.encrypted_dek,
            api_key_nonce=key.api_key_nonce,
            dek_nonce=key.dek_nonce,
        )
    )


async def delete_api_key(
    uow: IProjectUnitOfWork, project_id: int, user_id: int, api_key_id: int
) -> None:
    project, member = await _require_project_member(uow, project_id, user_id)
    key = await uow.api_key_repository.get_api_key(api_key_id)
    if key is None or (
        key.project_id != project_id and key.member_id != member.id
    ):
        raise ApiKeyNotFoundException(api_key_id)
    if key.project_id == project_id and project.owner_id != user_id:
        raise InsufficientProjectPermissionException('api_key:delete')
    await uow.api_key_repository.delete_api_key(api_key_id)
    await uow.commit()
