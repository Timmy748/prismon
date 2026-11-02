from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from project.entities.registry import mapper_registry


@mapper_registry.mapped_as_dataclass
class ProjectResourceEvent:
    __tablename__ = 'project_resource_events'
    __table_args__ = (
        UniqueConstraint(
            'idempotency_key', name='uq_project_resource_events_idempotency_key'
        ),
        Index(
            'ix_project_resource_events_resource_created',
            'project_id',
            'resource_type',
            'resource_id',
            'created_at',
            'id',
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    project_id: Mapped[int] = mapped_column(
        ForeignKey('projects.id', ondelete='CASCADE'), index=True
    )
    resource_type: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[int] = mapped_column(Integer)
    author_member_id: Mapped[int] = mapped_column(
        ForeignKey('members.id'), index=True
    )
    event_type: Mapped[str] = mapped_column(String(64))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default_factory=dict)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(512), default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=lambda: datetime.now(timezone.utc),
        init=False,
    )
