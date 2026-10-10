import binascii
import json
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

        # A CookieJar of Cookies the server sent back.
        self.cookies = cookiejar_from_dict({})

        # Encoding used to decode .text, taken from the charset of the Content-Type header. Set it to decode the body
        # with another encoding; None means UTF-8.
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


def build_response(res: dict[str, Any], res_cookies: RequestsCookieJar) -> Response:
    """Builds a Response object"""
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
    # Decode .text with the charset the server declared, if any
    content_type = response_headers.get("Content-Type")
    if content_type:
        response.encoding = _charset(content_type if isinstance(content_type, str) else content_type[0])
    # Add cookies
    response.cookies = res_cookies
    # Add response content (bytes)
    # With isByteResponse the library sends "data:<mime type>;base64,<payload>". It sniffs that mime type from the
    # bytes, which is why .encoding comes from the Content-Type header instead.
    body: str = res["body"]
    prefix, _, payload = body.partition(",")
    if prefix.startswith("data:") and prefix.endswith(";base64"):
        # a2b_base64 reads an ASCII str in place, without encoding a copy first.
        response._content = binascii.a2b_base64(payload)
    else:
        # Not a data URI: the body is plain text.
        response._content = body.encode()
    return response
