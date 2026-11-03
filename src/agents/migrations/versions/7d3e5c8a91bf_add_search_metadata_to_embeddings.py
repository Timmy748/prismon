"""add project and status metadata to resource embeddings

Revision ID: 7d3e5c8a91bf
Revises: 32fdc9aa8412
Create Date: 2026-11-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '7d3e5c8a91bf'
down_revision: Union[str, Sequence[str], None] = '32fdc9aa8412'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'document_embeddings',
        sa.Column('project_id', sa.Integer(), nullable=True),
    )
    op.add_column(
        'document_embeddings',
        sa.Column('status', sa.String(length=32), nullable=True),
    )
    op.add_column(
        'asset_embeddings',
        sa.Column('project_id', sa.Integer(), nullable=True),
    )
    op.add_column(
        'asset_embeddings',
        sa.Column('status', sa.String(length=32), nullable=True),
    )

    op.create_index(
        'ix_document_embeddings_search_bm25',
        'document_embeddings',
        ['document_id', 'content', 'project_id', 'status'],
        postgresql_using='paradedb',
    )
    op.create_index(
        'ix_asset_embeddings_search_bm25',
        'asset_embeddings',
        ['asset_id', 'content', 'project_id', 'status'],
        postgresql_using='paradedb',
    )


def downgrade() -> None:
    op.drop_index(
        'ix_asset_embeddings_search_bm25', table_name='asset_embeddings'
    )
    op.drop_index(
        'ix_document_embeddings_search_bm25',
        table_name='document_embeddings',
    )
    op.drop_column('asset_embeddings', 'status')
    op.drop_column('asset_embeddings', 'project_id')
    op.drop_column('document_embeddings', 'status')
    op.drop_column('document_embeddings', 'project_id')
