from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from project.entities.registry import mapper_registry


class AssetStatus(str, Enum):
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
    file: Mapped[str] = mapped_column(String(256))
    type: Mapped[str] = mapped_column(String(256))
    description: Mapped[Optional[str]] = mapped_column(
        String(256), default=None
    )
    status: Mapped[AssetStatus] = mapped_column(default=AssetStatus.ACTIVE)
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
