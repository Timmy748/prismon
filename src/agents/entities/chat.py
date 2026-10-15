from datetime import datetime

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from agents.entities.registry import mapper_registry


@mapper_registry.mapped_as_dataclass
class Chat:
    __tablename__ = 'chats'
    __table_args__ = (
        Index(
            'ix_chats_project_updated_at_id', 'project_id', 'updated_at', 'id'
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    title: Mapped[str] = mapped_column(String(256))
    project_id: Mapped[int] = mapped_column(index=True)
    owner: Mapped[int] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), insert_default=func.now(), init=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        init=False,
    )
