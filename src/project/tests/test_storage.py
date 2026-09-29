from pathlib import Path

import pytest

from project.storage import IStorage, LocalStorage


def test_local_storage_satisfies_interface(tmp_path: Path) -> None:
    storage: IStorage = LocalStorage(tmp_path)

    storage.save('file.bin', b'content')

    assert storage.retrieve('file.bin') == b'content'


def test_save_creates_parent_directories_and_overwrites_file(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path)

    storage.save('nested/file.bin', b'first')
    storage.save('nested/file.bin', b'second')

    assert (tmp_path / 'nested/file.bin').read_bytes() == b'second'


def test_retrieve_returns_none_when_file_does_not_exist(
    tmp_path: Path,
) -> None:
    assert LocalStorage(tmp_path).retrieve('missing.bin') is None


def test_delete_removes_file(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    storage.save('file.bin', b'content')

    storage.delete('file.bin')

    assert storage.retrieve('file.bin') is None


def test_delete_returns_none_when_file_does_not_exist(
    tmp_path: Path,
) -> None:
    assert LocalStorage(tmp_path).delete('missing.bin') is None


@pytest.mark.parametrize('key', ['../outside.bin', '/outside.bin'])
def test_rejects_keys_outside_storage_root(tmp_path: Path, key: str) -> None:
    storage = LocalStorage(tmp_path / 'storage')

    with pytest.raises(ValueError, match='within the storage root'):
        storage.retrieve(key)
