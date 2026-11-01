"""Create project tags and asset/document tag links.

Revision ID: f62e3c8d9a41
Revises: e4319b8c122f
"""
from alembic import op
import sqlalchemy as sa


revision = 'f62e3c8d9a41'
down_revision = 'e4319b8c122f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'tags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=128), nullable=False),
        sa.Column('description', sa.String(length=256), nullable=False),
        sa.Column('color', sa.String(length=7), nullable=False),
        sa.ForeignKeyConstraint(
            ['project_id'], ['projects.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_tags_project_id_label', 'tags', ['project_id', 'label']
    )
    op.create_table(
        'asset_tags',
        sa.Column('asset_id', sa.Integer(), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('asset_id', 'tag_id'),
    )
    op.create_index('ix_asset_tags_tag_id', 'asset_tags', ['tag_id'])
    op.create_table(
        'document_tags',
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ['document_id'], ['documents.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('document_id', 'tag_id'),
    )
    op.create_index(
        'ix_document_tags_tag_id', 'document_tags', ['tag_id']
    )


def downgrade() -> None:
    op.drop_index('ix_document_tags_tag_id', table_name='document_tags')
    op.drop_table('document_tags')
    op.drop_index('ix_asset_tags_tag_id', table_name='asset_tags')
    op.drop_table('asset_tags')
    op.drop_index('ix_tags_project_id_label', table_name='tags')
    op.drop_table('tags')
