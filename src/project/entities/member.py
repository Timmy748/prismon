from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from project.entities.registry import mapper_registry


class MemberRole(str, Enum):
    OWNER = 'owner'
    DIRECTOR = 'director'
    MEMBER = 'member'
    VIEWER = 'viewer'


class MemberStatus(str, Enum):
    PENDING = 'pending'
    ACTIVE = 'active'


@mapper_registry.mapped_as_dataclass
class Member:
    __tablename__ = 'members'
    __table_args__ = (
        Index(
            'ix_members_project_updated_at_id', 'project_id', 'updated_at', 'id'
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    project_id: Mapped[int] = mapped_column(
        ForeignKey('projects.id', ondelete='CASCADE')
    )
    user_id: Mapped[int] = mapped_column(index=True)
    role: Mapped[MemberRole] = mapped_column(default=MemberRole.MEMBER)
    status: Mapped[MemberStatus] = mapped_column(default=MemberStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=lambda: datetime.now(timezone.utc),
        init=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        init=False,
    )
