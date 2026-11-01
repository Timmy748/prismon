from infra.logs import get_logger
from project.dtos.page import PaginationDTO
from project.dtos.tag import CreateTagDTO, TagDTO, UpdateTagDTO
from project.entities.member import MemberStatus
from project.exceptions import (
    AssetNotFoundException,
    DocumentNotFoundException,
    InsufficientProjectPermissionException,
    ProjectNotFoundException,
    TagNotFoundException,
)
from project.permissions import ProjectPermission, has_permission
from project.unit_of_work import IProjectUnitOfWork

logger = get_logger(__name__)


async def _authorize(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    permission: ProjectPermission,
):
    if await uow.project_repository.get_project(project_id) is None:
        raise ProjectNotFoundException(project_id)
    members = await uow.member_repository.get_members(
        project_id,
        pagination=PaginationDTO(limit=100),
        user_id=user_id,
        status=MemberStatus.ACTIVE,
    )
    if not members.items:
        raise ProjectNotFoundException(project_id)
    member = members.items[0]
    if not has_permission(member.role, permission):
        logger.warning(
            'Tag permission denied: project_id=%s permission=%s',
            project_id,
            permission.value,
        )
        raise InsufficientProjectPermissionException(permission.value)
    return member


async def get_tags(
    uow: IProjectUnitOfWork, project_id: int, user_id: int
) -> list[TagDTO]:
    await _authorize(uow, project_id, user_id, ProjectPermission.TAG_READ)
    tags = await uow.tag_repository.get_tags(project_id)
    logger.info(
        'Project tags loaded: project_id=%s count=%s', project_id, len(tags)
    )
    return tags


async def add_tag(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    data: CreateTagDTO,
) -> TagDTO:
    await _authorize(uow, project_id, user_id, ProjectPermission.TAG_CREATE)
    tag = await uow.tag_repository.create_tag(
        project_id, data.label, data.description, data.color
    )
    await uow.commit()
    logger.info(
        'Project tag created: project_id=%s tag_id=%s', project_id, tag.id
    )
    return tag


async def update_tag(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    tag_id: int,
    data: UpdateTagDTO,
) -> TagDTO:
    await _authorize(uow, project_id, user_id, ProjectPermission.TAG_UPDATE)
    tag = await uow.tag_repository.get_tag(tag_id)
    if tag is None or tag.project_id != project_id:
        raise TagNotFoundException(tag_id)
    updated = await uow.tag_repository.update_tag(
        tag_id,
        label=data.label,
        description=data.description,
        color=data.color,
    )
    if updated is None:
        raise TagNotFoundException(tag_id)
    await uow.commit()
    logger.info(
        'Project tag updated: project_id=%s tag_id=%s', project_id, tag_id
    )
    return updated


async def delete_tag(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    tag_id: int,
) -> None:
    await _authorize(uow, project_id, user_id, ProjectPermission.TAG_DELETE)
    tag = await uow.tag_repository.get_tag(tag_id)
    if tag is None or tag.project_id != project_id:
        raise TagNotFoundException(tag_id)
    await uow.tag_repository.delete_tag(tag_id)
    await uow.commit()
    logger.info(
        'Project tag deleted: project_id=%s tag_id=%s', project_id, tag_id
    )


async def _get_asset(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    asset_id: int,
    permission: ProjectPermission,
):
    await _authorize(uow, project_id, user_id, permission)
    asset = await uow.asset_repository.get_asset(asset_id)
    if asset is None or asset.project_id != project_id:
        raise AssetNotFoundException(asset_id)
    return asset


async def _get_document(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    document_id: int,
    permission: ProjectPermission,
):
    await _authorize(uow, project_id, user_id, permission)
    document = await uow.document_repository.get_document(document_id)
    if document is None or document.project_id != project_id:
        raise DocumentNotFoundException(document_id)
    return document


async def _get_project_tag(
    uow: IProjectUnitOfWork, project_id: int, tag_id: int
) -> TagDTO:
    tag = await uow.tag_repository.get_tag(tag_id)
    if tag is None or tag.project_id != project_id:
        raise TagNotFoundException(tag_id)
    return tag


async def get_asset_tags(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    asset_id: int,
) -> list[TagDTO]:
    await _get_asset(
        uow, project_id, user_id, asset_id, ProjectPermission.ASSET_READ
    )
    tags = await uow.tag_repository.get_asset_tags(asset_id)
    logger.info(
        'Asset tags loaded: project_id=%s asset_id=%s count=%s',
        project_id,
        asset_id,
        len(tags),
    )
    return tags


async def attach_asset_tag(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    asset_id: int,
    tag_id: int,
) -> None:
    await _get_asset(
        uow,
        project_id,
        user_id,
        asset_id,
        ProjectPermission.ASSET_TAG_ASSIGN,
    )
    await _get_project_tag(uow, project_id, tag_id)
    await uow.tag_repository.attach_asset_tag(asset_id, tag_id)
    await uow.commit()
    logger.info(
        'Tag attached to asset: project_id=%s asset_id=%s tag_id=%s',
        project_id,
        asset_id,
        tag_id,
    )


async def detach_asset_tag(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    asset_id: int,
    tag_id: int,
) -> None:
    await _get_asset(
        uow,
        project_id,
        user_id,
        asset_id,
        ProjectPermission.ASSET_TAG_ASSIGN,
    )
    await _get_project_tag(uow, project_id, tag_id)
    await uow.tag_repository.detach_asset_tag(asset_id, tag_id)
    await uow.commit()
    logger.info(
        'Tag detached from asset: project_id=%s asset_id=%s tag_id=%s',
        project_id,
        asset_id,
        tag_id,
    )


async def get_document_tags(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    document_id: int,
) -> list[TagDTO]:
    await _get_document(
        uow,
        project_id,
        user_id,
        document_id,
        ProjectPermission.DOCUMENT_READ,
    )
    tags = await uow.tag_repository.get_document_tags(document_id)
    logger.info(
        'Document tags loaded: project_id=%s document_id=%s count=%s',
        project_id,
        document_id,
        len(tags),
    )
    return tags


async def attach_document_tag(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    document_id: int,
    tag_id: int,
) -> None:
    await _get_document(
        uow,
        project_id,
        user_id,
        document_id,
        ProjectPermission.DOCUMENT_TAG_ASSIGN,
    )
    await _get_project_tag(uow, project_id, tag_id)
    await uow.tag_repository.attach_document_tag(document_id, tag_id)
    await uow.commit()
    logger.info(
        'Tag attached to document: project_id=%s document_id=%s tag_id=%s',
        project_id,
        document_id,
        tag_id,
    )


async def detach_document_tag(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    document_id: int,
    tag_id: int,
) -> None:
    await _get_document(
        uow,
        project_id,
        user_id,
        document_id,
        ProjectPermission.DOCUMENT_TAG_ASSIGN,
    )
    await _get_project_tag(uow, project_id, tag_id)
    await uow.tag_repository.detach_document_tag(document_id, tag_id)
    await uow.commit()
    logger.info(
        'Tag detached from document: project_id=%s document_id=%s tag_id=%s',
        project_id,
        document_id,
        tag_id,
    )
