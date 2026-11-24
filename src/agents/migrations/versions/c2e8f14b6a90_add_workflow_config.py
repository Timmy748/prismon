"""Create a configuration table for workflows.

Revision ID: c2e8f14b6a90
Revises: 7d3e5c8a91bf
Create Date: 2026-11-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c2e8f14b6a90'
down_revision: Union[str, Sequence[str], None] = '7d3e5c8a91bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'workflow_configs',
        sa.Column('workflow_id', sa.Integer(), nullable=False),
        sa.Column(
            'config',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['workflow_id'], ['workflows.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('workflow_id'),
    )


def downgrade() -> None:
    op.drop_table('workflow_configs')
