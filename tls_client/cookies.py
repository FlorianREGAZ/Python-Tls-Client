from .structures import CaseInsensitiveDict

from http.cookiejar import CookieJar, Cookie
from urllib.parse import urlparse, urlunparse


class MockRequest:
    """
    Mimic a urllib2.Request to get the correct cookie string for the request.
    """

    def __init__(self, request_url: str, request_headers: CaseInsensitiveDict):
        self.request_url = request_url
        self.request_headers = request_headers
        self._new_headers = {}
        self.type = urlparse(self.request_url).scheme

    def get_type(self):
        return self.type

    def get_host(self):
        return urlparse(self.request_url).netloc

    def get_origin_req_host(self):
        return self.get_host()

    def get_full_url(self):
        # Only return the response's URL if the user hadn't set the Host
        # header
        if not self.request_headers.get("Host"):
            return self.request_url
        # If they did set it, retrieve it and reconstruct the expected domain
        host = self.request_headers["Host"]
        parsed = urlparse(self.request_url)
        # Reconstruct the URL as we expect it
        return urlunparse(
            [
                parsed.scheme,
                host,
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment,
            ]
        )

    def is_unverifiable(self):
        return True

    def has_header(self, name):
        return name in self.request_headers or name in self._new_headers

    def get_header(self, name, default=None):
        return self.request_headers.get(name, self._new_headers.get(name, default))

    def add_header(self, key, val):
        """cookielib has no legitimate use for this method; add it back if you find one."""
        raise NotImplementedError(
            "Cookie headers should be added with add_unredirected_header()"
        )

    def add_unredirected_header(self, name, value):
        self._new_headers[name] = value

    def get_new_headers(self):
        return self._new_headers

    @property
    def unverifiable(self):
        return self.is_unverifiable()

    @property
    def origin_req_host(self):
        return self.get_origin_req_host()

    @property
    def host(self):
        return self.get_host()


class MockResponse:
    """Wraps a `httplib.HTTPMessage` to mimic a `urllib.addinfourl`.

    ...what? Basically, expose the parsed HTTP headers from the server response
    the way `cookielib` expects to see them.
    """

    def __init__(self, headers):
        """Make a MockResponse for `cookielib` to read.

        :param headers: a httplib.HTTPMessage or analogous carrying the headers
        """
        self._headers = headers

    def info(self):
        return self._headers

    def getheaders(self, name):
        self._headers.getheaders(name)


def cookiejar_from_dict(cookie_dict: dict) -> CookieJar:
    """transform a dict to CookieJar"""
    cookie_jar = CookieJar()
    if cookie_dict is not None:
        for name, value in cookie_dict.items():
            cookie_jar.set_cookie(
                Cookie(
                    version=0,
                    name=name,
                    value=value,
                    port=None,
                    port_specified=False,
                    domain="",
                    domain_specified=False,
                    domain_initial_dot=False,
                    path="/",
                    path_specified=False,
                    secure=False,
                    expires=None,
                    discard=True,
                    comment=None,
                    comment_url=None,
                    rest={"HttpOnly": None},
                    rfc2109=False,
                )
            )
    return cookie_jar


def merge_cookies(cookiejar: CookieJar, cookies: dict) -> CookieJar:
    """Merge cookies in session and cookies provided in request"""
    cookies = cookiejar_from_dict(cookies)

    for cookie in cookies:
        cookiejar.set_cookie(cookie)

    return cookiejar


def get_cookie_header(request_url: str, request_headers: CaseInsensitiveDict, cookie_jar: CookieJar) -> str:
    r = MockRequest(request_url, request_headers)
    cookie_jar.add_cookie_header(r)
    return r.get_new_headers().get("Cookie")