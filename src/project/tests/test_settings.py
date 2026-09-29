import pytest

from project.settings import get_settings


def test_get_settings_reads_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('DATABASE_URL', 'sqlite+aiosqlite:///:memory:')
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.database_url == 'sqlite+aiosqlite:///:memory:'
    get_settings.cache_clear()
