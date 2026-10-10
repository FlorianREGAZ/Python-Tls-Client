"""multipart/form-data bodies for the files argument, laid out the way requests and urllib3 lay them out."""

import mimetypes
import os
import secrets
from collections.abc import Iterable, Mapping
from typing import Any, Protocol, TypeAlias, TypeVar

from .structures import CaseInsensitiveDict

_T = TypeVar("_T")


class _Readable(Protocol):
    def read(self) -> bytes | str: ...


# A file object (binary or text mode), bytes, or a str. Text is sent UTF-8 encoded.
FileContent: TypeAlias = _Readable | bytes | bytearray | str
# A file object on its own, or (filename, content[, content type[, extra part headers]]).
# A None filename sends a plain form field, a None content skips the field.
FileSpec: TypeAlias = (
    FileContent
    | tuple[str | None, FileContent | None]
    | tuple[str | None, FileContent | None, str | None]
    | tuple[str | None, FileContent | None, str | None, Mapping[str, str]]
)
# Field name -> file, or a list of (field name, file) pairs to send a field more than once.
Files: TypeAlias = Mapping[str, FileSpec] | Iterable[tuple[str, FileSpec]]
# Form fields sent before the files. A list value sends the field once per item.
Fields: TypeAlias = Mapping[str, Any] | Iterable[tuple[str, Any]]

_Part: TypeAlias = tuple[CaseInsensitiveDict[str], bytes]


def choose_boundary() -> str:
    return secrets.token_hex(16)


def encode_multipart(fields: Fields | None, files: Files) -> tuple[bytes, str]:
    """Returns the body and its Content-Type header for the form fields followed by the files."""
    boundary = choose_boundary()
    body = bytearray()
    for headers, content in [*_field_parts(fields or {}), *_file_parts(files)]:
        body += f"--{boundary}\r\n".encode()
        for name, value in headers.items():
            body += f"{name}: {value}\r\n".encode()
        body += b"\r\n" + content + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def _field_parts(fields: Fields) -> Iterable[_Part]:
    for name, value in _pairs(fields):
        values = [value] if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Iterable) else value
        for item in values:
            if item is not None:
                yield _part(name, None, item if isinstance(item, (bytes, bytearray)) else str(item))


def _file_parts(files: Files) -> Iterable[_Part]:
    for name, spec in _pairs(files):
        content_type = None
        extra_headers = None
        if isinstance(spec, (tuple, list)):
            if len(spec) == 2:
                filename, content = spec
            elif len(spec) == 3:
                filename, content, content_type = spec
            else:
                filename, content, content_type, extra_headers = spec
        else:
            filename, content = _guess_filename(spec) or name, spec

        if content is None:
            continue
        if not isinstance(content, (str, bytes, bytearray)):
            content = content.read()
        yield _part(name, filename, content, content_type, extra_headers)


def _part(
    name: str,
    filename: str | None,
    content: str | bytes | bytearray,
    content_type: str | None = None,
    extra_headers: Mapping[str, str] | None = None,
) -> _Part:
    disposition = f"form-data; {_quote('name', name)}"
    if filename is not None:
        disposition += f"; {_quote('filename', filename)}"
    headers = CaseInsensitiveDict({"Content-Disposition": disposition})
    if filename is not None:
        headers["Content-Type"] = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    headers.update(extra_headers or {})
    if content_type is not None:
        headers["Content-Type"] = content_type
    return headers, content.encode() if isinstance(content, str) else bytes(content)


def _quote(key: str, value: str) -> str:
    # Percent-escape ", CR and LF as the HTML standard, browsers and urllib3 do. Non-ASCII stays as is, sent as UTF-8.
    return f'{key}="{value.translate({10: "%0A", 13: "%0D", 34: "%22"})}"'


def _guess_filename(fileobj: object) -> str | None:
    # Like requests: the basename of an open file, but not pseudo names such as "<stdin>" or a descriptor number.
    name = getattr(fileobj, "name", None)
    if isinstance(name, str) and name and name[0] != "<" and name[-1] != ">":
        return os.path.basename(name)
    return None


def _pairs(items: Mapping[str, _T] | Iterable[tuple[str, _T]]) -> Iterable[tuple[str, _T]]:
    return items.items() if isinstance(items, Mapping) else items
