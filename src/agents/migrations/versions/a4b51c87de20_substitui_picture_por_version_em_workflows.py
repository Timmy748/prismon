"""Substitui picture por version em workflows.

Revision ID: a4b51c87de20
Revises: 7cab071e718a
Create Date: 2026-10-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a4b51c87de20'
down_revision: Union[str, Sequence[str], None] = '7cab071e718a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('workflows', 'picture')
    op.add_column(
        'workflows', sa.Column('version', sa.String(length=64), nullable=False)
    )


def downgrade() -> None:
    op.drop_column('workflows', 'version')
    op.add_column(
        'workflows',
        sa.Column('picture', sa.String(length=256), nullable=False),
    )
