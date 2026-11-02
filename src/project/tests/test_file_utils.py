import pytest

from project.utils.files import (
    build_download_filename,
    file_extension,
    normalize_filename,
)


@pytest.mark.parametrize(
    ('filename', 'expected'),
    [
        ('/home/user/texto.md', 'texto.md'),
        (r'C:\Users\user\texto.md', 'texto.md'),
        ('texto\n.md', 'texto.md'),
    ],
)
def test_normalize_filename_returns_safe_basename(filename, expected):
    assert normalize_filename(filename) == expected


def test_normalize_filename_uses_fallback_for_empty_basename():
    assert normalize_filename('/\r\n', fallback='document-42') == (
        'document-42'
    )


@pytest.mark.parametrize(
    ('filename', 'content_type', 'expected'),
    [
        ('texto.md', 'text/plain', 'md'),
        ('texto', 'text/markdown; charset=utf-8', 'md'),
        ('texto', 'text/plain', 'txt'),
        ('texto', 'application/octet-stream', None),
        ('texto.bad extension', 'text/plain', None),
    ],
)
def test_file_extension_uses_safe_filename_or_content_type(
    filename, content_type, expected
):
    assert file_extension(filename, content_type) == expected


@pytest.mark.parametrize(
    ('title', 'extension', 'expected'),
    [
        ('texto', 'md', 'texto.md'),
        ('texto.md', 'md', 'texto.md'),
        ('texto', None, 'texto'),
        ('/unsafe\nname', 'txt', 'unsafename.txt'),
        ('texto', 'bad extension', 'texto'),
        ('', 'pdf', 'download.pdf'),
    ],
)
def test_build_download_filename_combines_title_and_extension(
    title, extension, expected
):
    assert build_download_filename(title, extension, 'download') == expected
