from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from agents.embedding_engine.ollama import EMBEDDING_DIMENSION
from agents.entities.registry import mapper_registry


@mapper_registry.mapped_as_dataclass
class AssetEmbedding:
    __tablename__ = 'asset_embeddings'
    __table_args__ = (
        Index(
            'ix_asset_embeddings_embedding_hnsw',
            'embedding',
            postgresql_using='hnsw',
            postgresql_ops={'embedding': 'halfvec_ip_ops'},
        ),
    )

    asset_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content: Mapped[str] = mapped_column(Text())
    embedding: Mapped[list[float]] = mapped_column(HALFVEC(EMBEDDING_DIMENSION))
