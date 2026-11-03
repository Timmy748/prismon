"""add resource embedding tables and postgres extensions

Revision ID: 32fdc9aa8412
Revises: a4b51c87de20
Create Date: 2026-11-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import HALFVEC

revision: str = '32fdc9aa8412'
down_revision: Union[str, Sequence[str], None] = 'a4b51c87de20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_search CASCADE')

    op.create_table(
        'document_embeddings',
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', HALFVEC(256), nullable=False),
        sa.PrimaryKeyConstraint('document_id'),
    )
    op.create_index(
        'ix_document_embeddings_embedding_hnsw',
        'document_embeddings',
        ['embedding'],
        unique=False,
        postgresql_using='hnsw',
        postgresql_ops={'embedding': 'halfvec_ip_ops'},
    )

    op.create_table(
        'asset_embeddings',
        sa.Column('asset_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', HALFVEC(256), nullable=False),
        sa.PrimaryKeyConstraint('asset_id'),
    )
    op.create_index(
        'ix_asset_embeddings_embedding_hnsw',
        'asset_embeddings',
        ['embedding'],
        unique=False,
        postgresql_using='hnsw',
        postgresql_ops={'embedding': 'halfvec_ip_ops'},
    )


def downgrade() -> None:
    op.drop_index(
        'ix_asset_embeddings_embedding_hnsw',
        table_name='asset_embeddings',
    )
    op.drop_table('asset_embeddings')
    op.drop_index(
        'ix_document_embeddings_embedding_hnsw',
        table_name='document_embeddings',
    )
    op.drop_table('document_embeddings')
