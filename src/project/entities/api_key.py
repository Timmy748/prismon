from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from project.entities.registry import mapper_registry


class ApiKeyProvider(str, Enum):
    OPENROUTER = 'openrouter'


@mapper_registry.mapped_as_dataclass
class ApiKey:
    __tablename__ = 'api_keys'
    __table_args__ = (
        Index('ix_api_keys_member_created_id', 'member_id', 'created_at', 'id'),
        Index(
            'ix_api_keys_project_created_id', 'project_id', 'created_at', 'id'
        ),
        CheckConstraint(
            '(member_id IS NOT NULL AND project_id IS NULL) OR '
            '(member_id IS NULL AND project_id IS NOT NULL)',
            name='ck_api_keys_one_owner',
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    provider: Mapped[ApiKeyProvider]
    api_hint: Mapped[str] = mapped_column(String(32))
    encrypted_api_key: Mapped[bytes] = mapped_column(LargeBinary, repr=False)
    encrypted_dek: Mapped[bytes] = mapped_column(LargeBinary, repr=False)
    api_key_nonce: Mapped[bytes] = mapped_column(LargeBinary, repr=False)
    dek_nonce: Mapped[bytes] = mapped_column(LargeBinary, repr=False)
    member_id: Mapped[int | None] = mapped_column(
        ForeignKey('members.id', ondelete='CASCADE'), default=None
    )
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey('projects.id', ondelete='CASCADE'), default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=lambda: datetime.now(timezone.utc),
        init=False,
    )
