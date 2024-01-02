from .cookies import cookiejar_from_dict, RequestsCookieJar
from .structures import CaseInsensitiveDict
from requests.exceptions import HTTPError
from http.cookiejar import CookieJar
from typing import Union
import json


class Response:
    """object, which contains the response to an HTTP request."""

    def __init__(self):

        # Reference of URL the response is coming from (especially useful with redirects)
        self.url = None

        # Integer Code of responded HTTP Status, e.g. 404 or 200.
        self.status_code = None

        # String of responded HTTP Body.
        self.text = None

        # Case-insensitive Dictionary of Response Headers.
        self.headers = CaseInsensitiveDict()

        # A CookieJar of Cookies the server sent back.
        self.cookies = cookiejar_from_dict({})
        self.reason = None
        self._content = False

    def __enter__(self):
        return self

    def __repr__(self):
        return f"<Response [{self.status_code}]>"

    def json(self, **kwargs):
        """parse response body to json (dict/list)"""
        return json.loads(self.text, **kwargs)
    
    def raise_for_status(self):
        """Raises :class:`HTTPError`, if one occurred."""

        http_error_msg = ""
        if isinstance(self.reason, bytes):
            # We attempt to decode utf-8 first because some servers
            # choose to localize their reason strings. If the string
            # isn't utf-8, we fall back to iso-8859-1 for all other
            # encodings. (See PR #3538)
            try:
                reason = self.reason.decode("utf-8")
            except UnicodeDecodeError:
                reason = self.reason.decode("iso-8859-1")
        else:
            reason = self.reason

        if 400 <= self.status_code < 500:
            http_error_msg = (
                f"{self.status_code} Client Error: {reason} for url: {self.url}"
            )

        elif 500 <= self.status_code < 600:
            http_error_msg = (
                f"{self.status_code} Server Error: {reason} for url: {self.url}"
            )

        if http_error_msg:
            raise HTTPError(http_error_msg, response=self)

    @property
    def content(self):
        """Content of the response, in bytes."""
        
        if self._content is False:
            if self._content_consumed:
                raise RuntimeError("The content for this response was already consumed")

            if self.status_code == 0:
                self._content = None
            else:
                self._content = b"".join(self.iter_content(10 * 1024)) or b""
        self._content_consumed = True
        return self._content


def build_response(res: Union[dict, list], res_cookies: RequestsCookieJar) -> Response:
    """Builds a Response object """
    response = Response()
    # Add target / url
    response.url = res["target"]
    # Add status code
    response.status_code = res["status"]
    # Add headers
    response_headers = {}
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
