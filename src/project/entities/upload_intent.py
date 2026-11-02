from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from project.entities.registry import mapper_registry


@mapper_registry.mapped_as_dataclass
class UploadIntent:
    __tablename__ = 'project_upload_intents'
    __table_args__ = (
        CheckConstraint(
            '(asset_id IS NOT NULL AND document_id IS NULL) OR '
            '(asset_id IS NULL AND document_id IS NOT NULL)',
            name='ck_project_upload_intents_single_resource',
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, init=False)
    project_id: Mapped[int] = mapped_column(
        ForeignKey('projects.id', ondelete='CASCADE'), index=True
    )
    object_key: Mapped[str] = mapped_column(String(512), unique=True)
    final_file_key: Mapped[str] = mapped_column(String(512), unique=True)
    started_by_member_id: Mapped[int] = mapped_column(
        ForeignKey('members.id'), index=True
    )
    target_status: Mapped[str] = mapped_column(String(32))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    asset_id: Mapped[int | None] = mapped_column(
        ForeignKey('assets.id', ondelete='CASCADE'),
        default=None,
        index=True,
        unique=True,
    )
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey('documents.id', ondelete='CASCADE'),
        default=None,
        index=True,
        unique=True,
    )
    previous_file_key: Mapped[str | None] = mapped_column(
        String(512), default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=lambda: datetime.now(timezone.utc),
        init=False,
    )
    file_extension: Mapped[str | None] = mapped_column(String(16), default=None)
    content_type: Mapped[str] = mapped_column(
        String(256), default='application/octet-stream'
    )
