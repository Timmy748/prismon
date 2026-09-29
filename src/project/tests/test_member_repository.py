import pytest

from project.dtos.page import PaginationDTO
from project.entities.member import MemberRole, MemberStatus
from project.repositories.member import MemberRepository


@pytest.mark.asyncio
async def test_create_and_get_member(
    member_repo: MemberRepository, sample_project
) -> None:
    user_id = 22
    created = await member_repo.create_member(
        sample_project.id, user_id=user_id, status=MemberStatus.ACTIVE
    )

    loaded = await member_repo.get_member(created.id)

    assert loaded is not None
    assert loaded.user_id == user_id
    assert loaded.status == MemberStatus.ACTIVE.value


@pytest.mark.asyncio
async def test_get_members_filters_and_uses_cursor(
    member_repo: MemberRepository, sample_project
) -> None:
    first = await member_repo.create_member(
        sample_project.id, user_id=31, status=MemberStatus.ACTIVE
    )
    second = await member_repo.create_member(
        sample_project.id, user_id=32, status=MemberStatus.PENDING
    )

    page = await member_repo.get_members(
        sample_project.id,
        pagination=PaginationDTO(limit=1),
        status=MemberStatus.PENDING,
    )
    filtered = await member_repo.get_members(sample_project.id, user_id=31)
    role_filtered = await member_repo.get_members(
        sample_project.id, role=MemberRole.MEMBER
    )

    assert [item.id for item in page.items] == [second.id]
    assert page.pagination.cursor is None
    assert page.pagination.more is False
    assert [item.id for item in filtered.items] == [first.id]
    expected_member_count = 2
    assert len(role_filtered.items) == expected_member_count


@pytest.mark.asyncio
async def test_update_and_delete_member(
    member_repo: MemberRepository, sample_project
) -> None:
    created = await member_repo.create_member(sample_project.id, user_id=41)

    updated = await member_repo.update_member(
        created.id, role=MemberRole.DIRECTOR, status=MemberStatus.ACTIVE
    )
    deleted = await member_repo.delete_member(created.id)

    assert updated is not None and updated.status == MemberStatus.ACTIVE.value
    assert deleted is None
    assert await member_repo.get_member(created.id) is None


@pytest.mark.asyncio
async def test_update_member_returns_none_when_missing(
    member_repo: MemberRepository,
) -> None:
    result = await member_repo.update_member(404, status=MemberStatus.ACTIVE)

    assert result is None


@pytest.mark.asyncio
async def test_delete_member_does_nothing_when_missing(
    member_repo: MemberRepository,
) -> None:
    result = await member_repo.delete_member(404)

    assert result is None


@pytest.mark.asyncio
async def test_member_cursor_returns_older_members(
    member_repo: MemberRepository, sample_project
) -> None:
    members = [
        await member_repo.create_member(sample_project.id, user_id=user_id)
        for user_id in range(51, 54)
    ]

    first_page = await member_repo.get_members(
        sample_project.id, pagination=PaginationDTO(limit=1)
    )
    second_page = await member_repo.get_members(
        sample_project.id,
        pagination=PaginationDTO(limit=1, cursor=first_page.pagination.cursor),
    )

    assert first_page.items[0].id == members[-1].id
    assert second_page.items[0].id == members[-2].id
    assert first_page.pagination.more is True
