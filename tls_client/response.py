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

        # String of responded HTTP Body.
        self.text: str = ""

        # Case-insensitive dictionary of Response Headers. Headers sent more than once map to a list of values.
        self.headers: CaseInsensitiveDict[str | list[str]] = CaseInsensitiveDict()

        # A CookieJar of Cookies the server sent back.
        self.cookies = cookiejar_from_dict({})

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
    # Add cookies
    response.cookies = res_cookies
    # Add response body
    response.text = res["body"]
    # Add response content (bytes)
    response._content = res["body"].encode()
    return response
