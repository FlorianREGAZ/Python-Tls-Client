import binascii
import json
import re
from typing import Any

from .cookies import RequestsCookieJar, cookiejar_from_dict
from .structures import CaseInsensitiveDict


class Response:
    """object, which contains the response to an HTTP request."""

    def __init__(self) -> None:
        # Reference of URL the response is coming from (especially useful with redirects)
        self.url: str = ""

        # Integer Code of responded HTTP Status, e.g. 404 or 200.
        self.status_code: int = 0

        # Case-insensitive dictionary of Response Headers. Headers sent more than once map to a list of values.
        self.headers: CaseInsensitiveDict[str | list[str]] = CaseInsensitiveDict()

        # A CookieJar of Cookies the server sent back, on every redirect that led to this response too.
        self.cookies = cookiejar_from_dict({})

        # Responses of the redirects followed to get this one, oldest first.
        self.history: list[Response] = []

        # Encoding used to decode .text: the charset of the Content-Type header, else a BOM or the charset the document
        # declares in a <meta> tag. Set it to decode the body with another encoding; None means UTF-8.
        self.encoding: str | None = None

        # Bytes of responded HTTP Body.
        self._content: bytes = b""

    def __enter__(self) -> "Response":
        return self

    def __repr__(self) -> str:
        return f"<Response [{self.status_code}]>"

    def json(self, **kwargs: Any) -> Any:
        """parse response body to json (dict/list)"""
        return json.loads(self.text, **kwargs)

    @property
    def content(self) -> bytes:
        """Content of the response, in bytes."""
        return self._content

    @property
    def text(self) -> str:
        """Content of the response, decoded with .encoding (UTF-8 if unset). Undecodable bytes become U+FFFD."""
        # Decoded on every access rather than stored, so a large body isn't kept twice.
        try:
            return str(self._content, self.encoding or "utf-8", errors="replace")
        except LookupError:
            # The server named a charset Python doesn't know.
            return str(self._content, "utf-8", errors="replace")


def _charset(content_type: str) -> str | None:
    """Charset parameter of a Content-Type header value, e.g. "ISO-8859-1" for "text/html; charset=ISO-8859-1"."""
    for param in content_type.split(";")[1:]:
        key, _, value = param.partition("=")
        if key.strip().lower() == "charset":
            return value.strip().strip("\"'") or None
    return None


# Byte order marks and the codec that decodes them (and drops the mark).
_BOMS = ((b"\xef\xbb\xbf", "utf-8-sig"), (b"\xff\xfe", "utf-16"), (b"\xfe\xff", "utf-16"))

# <meta charset="..."> and <meta http-equiv="Content-Type" content="...; charset=...">, and <?xml encoding="..."?>
_DECLARED_CHARSET = re.compile(
    rb"""<meta[^>]*?charset\s*=\s*["']?\s*([\w.:+-]+)|^\s*<\?xml[^>]*?encoding\s*=\s*["']([\w.:+-]+)""",
    re.IGNORECASE,
)

# Labels that browsers decode with a superset codec; GB2312 pages routinely contain GBK characters.
_CODEC_ALIASES = {"gb2312": "gbk", "gb_2312-80": "gbk"}


def _sniff_encoding(content: bytes, content_type: str) -> str | None:
    """Encoding from a BOM, or from a charset the document declares in its first 1024 bytes, like browsers do.

    The library used to do this before .text was decoded in Python, so pages that only name their charset in a
    <meta> tag keep decoding the same way.
    """
    for bom, codec in _BOMS:
        if content.startswith(bom):
            return codec
    if content_type and not any(kind in content_type.lower() for kind in ("html", "xml")):
        return None
    match = _DECLARED_CHARSET.search(content[:1024])
    if match is None:
        return None
    return (match.group(1) or match.group(2)).decode("ascii")


def _codec(label: str | None) -> str | None:
    return _CODEC_ALIASES.get(label.lower(), label) if label else None


def build_response(res: dict[str, Any], res_cookies: RequestsCookieJar) -> Response:
    """Builds a Response object. Pops the body from res, so a large body can be freed as soon as it's decoded."""
    response = Response()
    # Add target / url
    response.url = res["target"]
    # Add status code
    response.status_code = res["status"]
    # Add headers
    response_headers: CaseInsensitiveDict[str | list[str]] = CaseInsensitiveDict()
    if res["headers"] is not None:
        for header_key, header_value in res["headers"].items():
            if len(header_value) == 1:
                response_headers[header_key] = header_value[0]
            else:
                response_headers[header_key] = header_value
    response.headers = response_headers
    content_type_header = response_headers.get("Content-Type") or ""
    content_type = content_type_header if isinstance(content_type_header, str) else content_type_header[0]
    # Add cookies
    response.cookies = res_cookies
    # Add response content (bytes)
    # With isByteResponse the library sends "data:<mime type>;base64,<payload>". It sniffs that mime type from the
    # bytes, which is why .encoding comes from the Content-Type header instead.
    body: str = res.pop("body")
    prefix, _, payload = body.partition(",")
    if prefix.startswith("data:") and prefix.endswith(";base64"):
        # Free the data URI before decoding, so it isn't held next to both the payload and the bytes.
        del body
        # a2b_base64 reads an ASCII str in place, without encoding a copy first.
        response._content = binascii.a2b_base64(payload)
    else:
        # Not a data URI: the body is plain text.
        response._content = body.encode()
    # Decode .text with the charset the server declared, else the one the document declares, if any
    response.encoding = _codec(_charset(content_type) or _sniff_encoding(response._content, content_type))
    return response
