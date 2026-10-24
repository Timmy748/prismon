from pathlib import Path
from typing import Protocol

from core.logs import get_logger
from project.settings import get_settings

logger = get_logger(__name__)


class IStorage(Protocol):
    def save(self, key: str, content: bytes | None) -> None: ...

    def retrieve(self, key: str) -> bytes | None: ...

    def delete(self, key: str) -> None: ...


class LocalStorage:
    def __init__(self, root: Path | str) -> None:
        self._root = Path(root).resolve()
        logger.info('Local project storage initialized')

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
        logger.debug('Project file stored: size_bytes=%s', len(content))

    def retrieve(self, key: str) -> bytes | None:
        path = self._path_for(key)
        try:
            content = path.read_bytes()
            logger.debug('Project file retrieved: size_bytes=%s', len(content))
            return content
        except FileNotFoundError:
            logger.debug('Project file not found in storage')
            return None

    def delete(self, key: str) -> None:
        path = self._path_for(key)
        try:
            path.unlink()
            logger.debug('Project file deleted from storage')
        except FileNotFoundError:
            logger.debug('Project file was already absent from storage')
            return


def create_storage() -> IStorage:  # pragma: no cover
    return LocalStorage(get_settings().STORAGE_PATH)
