from unittest.mock import AsyncMock

import pytest

from project.dtos.member import ChangeRoleMemberDTO, ResumeInviteMemberDTO
from project.entities.member import MemberRole, MemberStatus
from project.exceptions import (
    InsufficientProjectPermissionException,
    InvalidInvitationStateException,
    MemberAlreadyExistsException,
    MemberNotFoundException,
    ProjectNotFoundException,
)
from project.use_cases.member import (
    change_member_role,
    get_members,
    invite_member,
    remove_member,
    respond_to_invitation,
)


async def _project_with_owner(project_repo, member_repo):
    project = await project_repo.create_project('Brand', 1)
    owner = await member_repo.create_member(
        project.id, 1, MemberRole.OWNER, MemberStatus.ACTIVE
    )
    return project, owner


@pytest.mark.asyncio
async def test_get_members_requires_membership_and_returns_page(
    project_repo, member_repo
):
    project, _ = await _project_with_owner(project_repo, member_repo)
    page = await get_members(project_repo, member_repo, project.id, 1)
    assert [member.user_id for member in page.items] == [1]
    with pytest.raises(ProjectNotFoundException):
        await get_members(project_repo, member_repo, project.id, 9)


@pytest.mark.asyncio
async def test_get_members_missing_project_is_hidden(project_repo, member_repo):
    with pytest.raises(ProjectNotFoundException):
        await get_members(project_repo, member_repo, 404, 1)


@pytest.mark.asyncio
async def test_invite_member_creates_pending_member(project_repo, member_repo):
    project, _ = await _project_with_owner(project_repo, member_repo)
    invitation = await invite_member(
        project_repo, member_repo, project.id, 1, 2
    )
    assert invitation.user_id == 2  # noqa: PLR2004
    assert invitation.status is MemberStatus.PENDING
    assert invitation.role is MemberRole.MEMBER


@pytest.mark.asyncio
async def test_invite_member_requires_invite_permission(
    project_repo, member_repo
):
    project = await project_repo.create_project('Brand', 1)
    await member_repo.create_member(
        project.id, 1, MemberRole.MEMBER, MemberStatus.ACTIVE
    )
    with pytest.raises(InsufficientProjectPermissionException):
        await invite_member(project_repo, member_repo, project.id, 1, 2)


@pytest.mark.asyncio
async def test_invite_member_rejects_existing_pending_member(
    project_repo, member_repo
):
    project, _ = await _project_with_owner(project_repo, member_repo)
    await member_repo.create_member(project.id, 2)
    with pytest.raises(MemberAlreadyExistsException):
        await invite_member(project_repo, member_repo, project.id, 1, 2)


@pytest.mark.asyncio
async def test_invite_member_raises_when_repository_does_not_create_member(
    project_repo, member_repo
):
    project, _ = await _project_with_owner(project_repo, member_repo)
    member_repo.create_member = AsyncMock(return_value=None)
    with pytest.raises(MemberNotFoundException):
        await invite_member(project_repo, member_repo, project.id, 1, 2)


@pytest.mark.asyncio
async def test_change_member_role_success(project_repo, member_repo):
    project, _ = await _project_with_owner(project_repo, member_repo)
    target = await member_repo.create_member(project.id, 2)
    result = await change_member_role(
        project_repo,
        member_repo,
        project.id,
        1,
        target.id,
        ChangeRoleMemberDTO('director'),
    )
    assert result.role is MemberRole.DIRECTOR


@pytest.mark.asyncio
async def test_change_member_role_checks_permission_and_target_scope(
    project_repo, member_repo
):
    project = await project_repo.create_project('Brand', 1)
    await member_repo.create_member(
        project.id, 1, MemberRole.MEMBER, MemberStatus.ACTIVE
    )
    with pytest.raises(InsufficientProjectPermissionException):
        await change_member_role(
            project_repo,
            member_repo,
            project.id,
            1,
            500,
            ChangeRoleMemberDTO('member'),
        )
    await member_repo.update_member(
        (await member_repo.get_members(project.id)).items[0].id,
        role=MemberRole.OWNER,
    )
    other_project = await project_repo.create_project('Other', 3)
    target = await member_repo.create_member(other_project.id, 4)
    with pytest.raises(MemberNotFoundException):
        await change_member_role(
            project_repo,
            member_repo,
            project.id,
            1,
            target.id,
            ChangeRoleMemberDTO('member'),
        )


@pytest.mark.asyncio
async def test_change_member_role_rejects_invalid_role(
    project_repo, member_repo
):
    project, _ = await _project_with_owner(project_repo, member_repo)
    target = await member_repo.create_member(project.id, 2)
    with pytest.raises(ValueError, match='Invalid member role'):
        await change_member_role(
            project_repo,
            member_repo,
            project.id,
            1,
            target.id,
            ChangeRoleMemberDTO('unknown'),
        )


@pytest.mark.asyncio
async def test_change_member_role_raises_when_update_returns_none(
    project_repo, member_repo
):
    project, _ = await _project_with_owner(project_repo, member_repo)
    target = await member_repo.create_member(project.id, 2)
    member_repo.update_member = AsyncMock(return_value=None)
    with pytest.raises(MemberNotFoundException):
        await change_member_role(
            project_repo,
            member_repo,
            project.id,
            1,
            target.id,
            ChangeRoleMemberDTO('director'),
        )


@pytest.mark.asyncio
async def test_accept_invitation_activates_membership(
    project_repo, member_repo
):
    project, _ = await _project_with_owner(project_repo, member_repo)
    invitation = await member_repo.create_member(project.id, 2)
    accepted = await respond_to_invitation(
        project_repo, member_repo, project.id, 2, ResumeInviteMemberDTO(True)
    )
    assert accepted.id == invitation.id
    assert accepted.status is MemberStatus.ACTIVE


@pytest.mark.asyncio
async def test_refuse_invitation_deletes_membership(project_repo, member_repo):
    project, _ = await _project_with_owner(project_repo, member_repo)
    invitation = await member_repo.create_member(project.id, 2)
    refused = await respond_to_invitation(
        project_repo, member_repo, project.id, 2, ResumeInviteMemberDTO(False)
    )
    assert refused.id == invitation.id
    assert await member_repo.get_member(invitation.id) is None


@pytest.mark.asyncio
async def test_respond_to_invitation_rejects_missing_or_nonpending(
    project_repo, member_repo
):
    with pytest.raises(ProjectNotFoundException):
        await respond_to_invitation(
            project_repo, member_repo, 400, 2, ResumeInviteMemberDTO(True)
        )
    project, _ = await _project_with_owner(project_repo, member_repo)
    with pytest.raises(InvalidInvitationStateException):
        await respond_to_invitation(
            project_repo,
            member_repo,
            project.id,
            2,
            ResumeInviteMemberDTO(True),
        )
    await member_repo.create_member(
        project.id, 2, MemberRole.MEMBER, MemberStatus.ACTIVE
    )
    with pytest.raises(InvalidInvitationStateException):
        await respond_to_invitation(
            project_repo,
            member_repo,
            project.id,
            2,
            ResumeInviteMemberDTO(True),
        )


@pytest.mark.asyncio
async def test_accept_invitation_raises_if_update_returns_none(
    project_repo, member_repo
):
    project, _ = await _project_with_owner(project_repo, member_repo)
    await member_repo.create_member(project.id, 2)
    member_repo.update_member = AsyncMock(return_value=None)
    with pytest.raises(InvalidInvitationStateException):
        await respond_to_invitation(
            project_repo,
            member_repo,
            project.id,
            2,
            ResumeInviteMemberDTO(True),
        )


@pytest.mark.asyncio
async def test_remove_member_requires_permission_and_project_scope(
    project_repo, member_repo
):
    project, _ = await _project_with_owner(project_repo, member_repo)
    target = await member_repo.create_member(project.id, 2)
    await remove_member(project_repo, member_repo, project.id, 1, target.id)
    assert await member_repo.get_member(target.id) is None
    with pytest.raises(MemberNotFoundException):
        await remove_member(project_repo, member_repo, project.id, 1, target.id)
    other = await project_repo.create_project('Other', 3)
    foreign = await member_repo.create_member(other.id, 4)
    with pytest.raises(MemberNotFoundException):
        await remove_member(
            project_repo, member_repo, project.id, 1, foreign.id
        )


@pytest.mark.asyncio
async def test_remove_member_denies_member_role(project_repo, member_repo):
    project = await project_repo.create_project('Brand', 1)
    await member_repo.create_member(
        project.id, 1, MemberRole.MEMBER, MemberStatus.ACTIVE
    )
    target = await member_repo.create_member(project.id, 2)
    with pytest.raises(InsufficientProjectPermissionException):
        await remove_member(project_repo, member_repo, project.id, 1, target.id)
