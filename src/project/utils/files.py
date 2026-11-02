import mimetypes
import re

_VALID_EXTENSION = re.compile(r'[a-z0-9][a-z0-9_-]{0,15}')
_COMMON_CONTENT_TYPE_EXTENSIONS = {
    'text/markdown': 'md',
    'text/plain': 'txt',
}


def normalize_filename(filename: str, fallback: str = 'download') -> str:
    """Return a safe basename suitable for persisted file metadata."""
    basename = filename.replace('\\', '/').rsplit('/', maxsplit=1)[-1]
    basename = ''.join(
        character
        for character in basename
        if character >= ' ' and character != '\x7f'
    ).strip()
    return basename or fallback


def file_extension(
    original_filename: str, content_type: str | None = None
) -> str | None:
    """Get a safe extension from the source filename or its media type."""
    basename = normalize_filename(original_filename, fallback='')
    suffix = basename.rpartition('.')[2] if '.' in basename else ''
    if suffix:
        extension = suffix.lower()
        return extension if _VALID_EXTENSION.fullmatch(extension) else None

    if content_type is None:
        return None
    media_type = content_type.partition(';')[0].strip().lower()
    extension = _COMMON_CONTENT_TYPE_EXTENSIONS.get(media_type)
    if extension is None and media_type != 'application/octet-stream':
        guessed = mimetypes.guess_extension(media_type, strict=True)
        extension = guessed.removeprefix('.').lower() if guessed else None
    if extension is None or not _VALID_EXTENSION.fullmatch(extension):
        return None
    return extension


def build_download_filename(
    title: str, extension: str | None, fallback: str
) -> str:
    """Combine a resource title with its normalized file extension."""
    filename = normalize_filename(title, fallback=fallback)
    if extension is None:
        return filename
    safe_extension = extension.lower().removeprefix('.')
    if not _VALID_EXTENSION.fullmatch(safe_extension):
        return filename
    suffix = f'.{safe_extension}'
    if filename.lower().endswith(suffix):
        return filename
    return f'{filename}{suffix}'
