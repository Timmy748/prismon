from sqlalchemy import Column, ForeignKey, Index, String, Table
from sqlalchemy.orm import Mapped, mapped_column

from project.entities.registry import mapper_registry


@mapper_registry.mapped_as_dataclass
class Tag:
    __tablename__ = 'tags'
    __table_args__ = (Index('ix_tags_project_id_label', 'project_id', 'label'),)

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    project_id: Mapped[int] = mapped_column(
        ForeignKey('projects.id', ondelete='CASCADE')
    )
    label: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(String(256))
    color: Mapped[str] = mapped_column(String(7))


asset_tags = Table(
    'asset_tags',
    mapper_registry.metadata,
    Column(
        'asset_id',
        ForeignKey('assets.id', ondelete='CASCADE'),
        primary_key=True,
    ),
    Column(
        'tag_id',
        ForeignKey('tags.id', ondelete='CASCADE'),
        primary_key=True,
    ),
    Index('ix_asset_tags_tag_id', 'tag_id'),
)

document_tags = Table(
    'document_tags',
    mapper_registry.metadata,
    Column(
        'document_id',
        ForeignKey('documents.id', ondelete='CASCADE'),
        primary_key=True,
    ),
    Column(
        'tag_id',
        ForeignKey('tags.id', ondelete='CASCADE'),
        primary_key=True,
    ),
    Index('ix_document_tags_tag_id', 'tag_id'),
)
