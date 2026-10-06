from pathlib import Path
from typing import Protocol

from project.settings import get_settings


class IStorage(Protocol):
    def save(self, key: str, content: bytes | None) -> None: ...

    def retrieve(self, key: str) -> bytes | None: ...

    def delete(self, key: str) -> None: ...


class LocalStorage:
    def __init__(self, root: Path | str) -> None:
        self._root = Path(root).resolve()

    def _path_for(self, key: str) -> Path:
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError('Storage key must stay within the storage root')
        return path

    def save(self, key: str, content: bytes | None) -> None:
        if content is None:
            return
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def retrieve(self, key: str) -> bytes | None:
        path = self._path_for(key)
        try:
            return path.read_bytes()
        except FileNotFoundError:
            return None

    def delete(self, key: str) -> None:
        path = self._path_for(key)
        try:
            path.unlink()
        except FileNotFoundError:
            return


def create_storage() -> IStorage:  # pragma: no cover
    return LocalStorage(get_settings().STORAGE_PATH)
