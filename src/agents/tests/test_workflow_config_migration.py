import importlib.util
from pathlib import Path
from unittest.mock import Mock

from sqlalchemy import Column, ForeignKeyConstraint, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import JSONB

MIGRATION_PATH = (
    Path(__file__).parents[1]
    / 'migrations'
    / 'versions'
    / 'c2e8f14b6a90_add_workflow_config.py'
)
SPEC = importlib.util.spec_from_file_location(
    'workflow_config_migration', MIGRATION_PATH
)
assert SPEC is not None and SPEC.loader is not None
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)


def test_upgrade_creates_one_to_one_jsonb_workflow_config_table(monkeypatch):
    operations = Mock()
    monkeypatch.setattr(migration, 'op', operations)

    migration.upgrade()

    args = operations.create_table.call_args.args
    assert args[0] == 'workflow_configs'
    columns = [arg for arg in args[1:] if isinstance(arg, Column)]
    assert [(column.name, column.nullable) for column in columns] == [
        ('workflow_id', False),
        ('config', False),
    ]
    assert isinstance(columns[1].type, JSONB)
    assert any(isinstance(arg, PrimaryKeyConstraint) for arg in args)
    foreign_key = next(
        arg for arg in args if isinstance(arg, ForeignKeyConstraint)
    )
    assert foreign_key._pending_colargs == ['workflow_id']
    assert foreign_key.elements[0].target_fullname == 'workflows.id'
    assert foreign_key.ondelete == 'CASCADE'


def test_migration_follows_current_alembic_head():
    assert migration.down_revision == '7d3e5c8a91bf'


def test_downgrade_drops_workflow_config_table(monkeypatch):
    operations = Mock()
    monkeypatch.setattr(migration, 'op', operations)

    migration.downgrade()

    operations.drop_table.assert_called_once_with('workflow_configs')
