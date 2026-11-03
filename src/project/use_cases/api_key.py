# ruff: noqa: PLR0913, PLR0917
from infra.logs import get_logger
from project.dtos.api_key import ApiKeyDTO, CreateApiKeyDTO
from project.dtos.api_key_hint import ApiKeyHintDTO
from project.dtos.page import CursorPage, PaginationDTO
from project.entities.api_key import ApiKeyProvider
from project.exceptions import (
    ApiKeyNotFoundException,
    InsufficientProjectPermissionException,
)
from project.permissions.actions import ApiKeyAction
from project.permissions.dispatcher import verify_resource_permission
from project.permissions.dtos import ApiKeyPermissionDTO
from project.security.api_key import EncryptedApiKey, IApiKeyEncryption
from project.unit_of_work import IProjectUnitOfWork
from project.use_cases.project import _require_project_member

logger = get_logger(__name__)

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
    logger.debug(
        'Encrypting project API key for storage: '
        'provider=%s member_id=%s project_id=%s',
        provider.value,
        member_id,
        project_id,
    )
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
    logger.info(
        'Project API key created: '
        'api_key_id=%s member_id=%s project_id=%s provider=%s',
        key.id,
        member_id,
        project_id,
        provider.value,
    )
    return _hint(key)


async def create_member_api_key(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    provider: ApiKeyProvider,
    api_key: str,
    encryptor: IApiKeyEncryption,
) -> ApiKeyHintDTO:
    logger.debug(
        'Creating member API key: project_id=%s user_id=%s provider=%s',
        project_id,
        user_id,
        provider.value,
    )
    _, member = await _require_project_member(uow, project_id, user_id)
    if not verify_resource_permission(
        member,
        ApiKeyPermissionDTO(None, member.id, None),
        ApiKeyAction.MEMBER_CREATE,
    ):
        raise InsufficientProjectPermissionException(
            ApiKeyAction.MEMBER_CREATE.value
        )
    return await _create(uow, provider, api_key, encryptor, member_id=member.id)


async def create_project_api_key(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    provider: ApiKeyProvider,
    api_key: str,
    encryptor: IApiKeyEncryption,
) -> ApiKeyHintDTO:
    logger.debug(
        'Creating project API key: project_id=%s user_id=%s provider=%s',
        project_id,
        user_id,
        provider.value,
    )
    project, member = await _require_project_member(uow, project_id, user_id)
    if not verify_resource_permission(
        member,
        ApiKeyPermissionDTO(project.id, None, project.owner_id),
        ApiKeyAction.PROJECT_CREATE,
    ):
        logger.warning(
            'Project API key creation denied: project_id=%s user_id=%s',
            project_id,
            user_id,
        )
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
    logger.debug(
        'Listing member API keys: project_id=%s user_id=%s',
        project_id,
        user_id,
    )
    _, member = await _require_project_member(uow, project_id, user_id)
    if not verify_resource_permission(
        member,
        ApiKeyPermissionDTO(None, member.id, None),
        ApiKeyAction.MEMBER_LIST,
    ):
        raise InsufficientProjectPermissionException(
            ApiKeyAction.MEMBER_LIST.value
        )
    page = await uow.api_key_repository.list_member_api_keys(
        member.id, pagination
    )
    result = CursorPage(
        items=[_hint(key) for key in page.items], pagination=page.pagination
    )
    logger.debug(
        'Member API keys listed: project_id=%s member_id=%s count=%s',
        project_id,
        member.id,
        len(result.items),
    )
    return result


async def list_project_api_keys(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    pagination: PaginationDTO = PaginationDTO(),
) -> CursorPage[ApiKeyHintDTO]:
    logger.debug(
        'Listing project API keys: project_id=%s user_id=%s',
        project_id,
        user_id,
    )
    project, member = await _require_project_member(uow, project_id, user_id)
    if not verify_resource_permission(
        member,
        ApiKeyPermissionDTO(project.id, None, project.owner_id),
        ApiKeyAction.PROJECT_LIST,
    ):
        raise InsufficientProjectPermissionException(
            ApiKeyAction.PROJECT_LIST.value
        )
    page = await uow.api_key_repository.list_project_api_keys(
        project_id, pagination
    )
    result = CursorPage(
        items=[_hint(key) for key in page.items], pagination=page.pagination
    )
    logger.debug(
        'Project API keys listed: project_id=%s count=%s',
        project_id,
        len(result.items),
    )
    return result


async def get_api_key(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    api_key_id: int,
    encryptor: IApiKeyEncryption,
) -> str:
    logger.debug(
        'Retrieving project API key: project_id=%s user_id=%s api_key_id=%s',
        project_id,
        user_id,
        api_key_id,
    )
    project, member = await _require_project_member(uow, project_id, user_id)
    key = await uow.api_key_repository.get_api_key(api_key_id)
    if key is None:
        logger.warning(
            'Project API key lookup failed: api_key_id=%s reason=not_found',
            api_key_id,
        )
        raise ApiKeyNotFoundException(api_key_id)
    permission_resource = ApiKeyPermissionDTO(
        key.project_id,
        key.member_id,
        project.owner_id if key.project_id is not None else None,
    )
    if not verify_resource_permission(
        member, permission_resource, ApiKeyAction.READ
    ):
        logger.warning(
            'Project API key lookup failed: '
            'api_key_id=%s reason=not_owned project_id=%s user_id=%s',
            api_key_id,
            project_id,
            user_id,
        )
        raise ApiKeyNotFoundException(api_key_id)

    secret = encryptor.decrypt(
        EncryptedApiKey(
            encrypted_api_key=key.encrypted_api_key,
            encrypted_dek=key.encrypted_dek,
            api_key_nonce=key.api_key_nonce,
            dek_nonce=key.dek_nonce,
        )
    )
    logger.debug(
        'Project API key retrieved: api_key_id=%s project_id=%s',
        api_key_id,
        project_id,
    )
    return secret


async def delete_api_key(
    uow: IProjectUnitOfWork, project_id: int, user_id: int, api_key_id: int
) -> None:
    logger.debug(
        'Deleting project API key: project_id=%s user_id=%s api_key_id=%s',
        project_id,
        user_id,
        api_key_id,
    )
    project, member = await _require_project_member(uow, project_id, user_id)
    key = await uow.api_key_repository.get_api_key(api_key_id)
    if key is None or (
        key.project_id != project_id and key.member_id != member.id
    ):
        logger.warning(
            'Project API key deletion failed: '
            'api_key_id=%s reason=not_found_or_not_owned '
            'project_id=%s user_id=%s',
            api_key_id,
            project_id,
            user_id,
        )
        raise ApiKeyNotFoundException(api_key_id)
    permission_resource = ApiKeyPermissionDTO(
        key.project_id,
        key.member_id,
        project.owner_id if key.project_id is not None else None,
    )
    if not verify_resource_permission(
        member, permission_resource, ApiKeyAction.DELETE
    ):
        logger.warning(
            'Project API key deletion denied: '
            'api_key_id=%s project_id=%s user_id=%s',
            api_key_id,
            project_id,
            user_id,
        )
        raise InsufficientProjectPermissionException('api_key:delete')
    await uow.api_key_repository.delete_api_key(api_key_id)
    await uow.commit()
    logger.info(
        'Project API key deleted: api_key_id=%s project_id=%s user_id=%s',
        api_key_id,
        project_id,
        user_id,
    )
