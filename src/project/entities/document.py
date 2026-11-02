from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from project.entities.registry import mapper_registry
from project.entities.tag import Tag, document_tags


class DocumentStatus(str, Enum):
    UPLOADING = 'uploading'
    FAILED = 'failed'
    DRAFT = 'draft'
    PENDING = 'pending'
    PUBLISHED = 'published'
    ARCHIVED = 'archived'


@mapper_registry.mapped_as_dataclass
class Document:
    __tablename__ = 'documents'
    __table_args__ = (
        Index(
            'ix_documents_project_updated_at_id',
            'project_id',
            'updated_at',
            'id',
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    project_id: Mapped[int] = mapped_column(
        ForeignKey('projects.id', ondelete='CASCADE')
    )
    created_by_member_id: Mapped[int] = mapped_column(
        ForeignKey('members.id'), index=True
    )
    file: Mapped[str | None] = mapped_column(String(256), nullable=True)
    name: Mapped[str] = mapped_column(String(256))
    file_extension: Mapped[str | None] = mapped_column(String(16), default=None)
    content_type: Mapped[str | None] = mapped_column(String(256), default=None)
    description: Mapped[Optional[str]] = mapped_column(
        String(256), default=None
    )
    status: Mapped[DocumentStatus] = mapped_column(default=DocumentStatus.DRAFT)
    tags: Mapped[list[Tag]] = relationship(
        secondary=document_tags,
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
