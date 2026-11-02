from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from project.entities.registry import mapper_registry
from project.entities.tag import Tag, asset_tags


class AssetStatus(str, Enum):
    UPLOADING = 'uploading'
    FAILED = 'failed'
    ACTIVE = 'active'
    PENDING = 'pending'
    ARCHIVED = 'archived'


@mapper_registry.mapped_as_dataclass
class Asset:
    __tablename__ = 'assets'
    __table_args__ = (
        Index(
            'ix_assets_project_updated_at_id', 'project_id', 'updated_at', 'id'
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    project_id: Mapped[int] = mapped_column(
        ForeignKey('projects.id', ondelete='CASCADE')
    )
    created_by_member_id: Mapped[int] = mapped_column(
        ForeignKey('members.id'), index=True
    )
    file: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    name: Mapped[str] = mapped_column(String(256))
    type: Mapped[str] = mapped_column(String(256))
    file_extension: Mapped[str | None] = mapped_column(String(16), default=None)
    content_type: Mapped[str | None] = mapped_column(String(256), default=None)
    description: Mapped[Optional[str]] = mapped_column(
        String(256), default=None
    )
    status: Mapped[AssetStatus] = mapped_column(default=AssetStatus.ACTIVE)
    tags: Mapped[list[Tag]] = relationship(
        secondary=asset_tags,
        lazy='selectin',
        default_factory=list,
    )
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
