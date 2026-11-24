from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agents.entities.registry import mapper_registry


@mapper_registry.mapped_as_dataclass
class Workflow:
    __tablename__ = 'workflows'

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    name: Mapped[str] = mapped_column(String(256), unique=True)
    description: Mapped[str] = mapped_column(Text)
    version: Mapped[str] = mapped_column(String(64))
    workflow_config: Mapped[WorkflowConfig | None] = relationship(
        back_populates='workflow',
        cascade='all, delete-orphan',
        default=None,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), insert_default=func.now(), init=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        init=False,
    )

    @property
    def config(self) -> dict[str, Any]:
        return self.workflow_config.config if self.workflow_config else {}

    @config.setter
    def config(self, value: dict[str, Any]) -> None:
        if self.workflow_config is None:
            self.workflow_config = WorkflowConfig(config=value)
        else:
            self.workflow_config.config = value


@mapper_registry.mapped_as_dataclass
class WorkflowConfig:
    __tablename__ = 'workflow_configs'

    workflow_id: Mapped[int] = mapped_column(
        ForeignKey('workflows.id', ondelete='CASCADE'),
        primary_key=True,
        init=False,
    )
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default_factory=dict)
    workflow: Mapped[Workflow] = relationship(
        back_populates='workflow_config', init=False
    )
