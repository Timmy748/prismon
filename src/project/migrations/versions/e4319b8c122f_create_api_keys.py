"""Create encrypted API keys.

Revision ID: e4319b8c122f
Revises: c103e0ceed08
"""
from alembic import op
import sqlalchemy as sa

revision = 'e4319b8c122f'
down_revision = 'c103e0ceed08'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'api_keys',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('provider', sa.Enum('OPENROUTER', name='apikeyprovider'), nullable=False),
        sa.Column('api_hint', sa.String(32), nullable=False),
        sa.Column('encrypted_api_key', sa.LargeBinary(), nullable=False),
        sa.Column('encrypted_dek', sa.LargeBinary(), nullable=False),
        sa.Column('api_key_nonce', sa.LargeBinary(), nullable=False),
        sa.Column('dek_nonce', sa.LargeBinary(), nullable=False),
        sa.Column('member_id', sa.Integer(), sa.ForeignKey('members.id', ondelete='CASCADE')),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            '(member_id IS NOT NULL AND project_id IS NULL) OR '
            '(member_id IS NULL AND project_id IS NOT NULL)',
            name='ck_api_keys_one_owner',
        ),
    )
    op.create_index('ix_api_keys_member_created_id', 'api_keys', ['member_id', 'created_at', 'id'])
    op.create_index('ix_api_keys_project_created_id', 'api_keys', ['project_id', 'created_at', 'id'])


def downgrade() -> None:
    op.drop_index('ix_api_keys_project_created_id', table_name='api_keys')
    op.drop_index('ix_api_keys_member_created_id', table_name='api_keys')
    op.drop_table('api_keys')
    sa.Enum(name='apikeyprovider').drop(op.get_bind(), checkfirst=True)
