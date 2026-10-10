import base64
import ctypes
import difflib
import urllib.parse
import uuid
from collections.abc import Mapping
from http.cookiejar import CookieJar
from json import dumps, loads
from typing import Any, TypeAlias

from .__version__ import __version__
from .cffi import destroySession, freeMemory, request
from .cookies import cookiejar_from_dict, extract_cookies_to_jar, get_cookie_header, merge_cookies
from .exceptions import TLSClientException, TooManyRedirects
from .multipart import Files, encode_multipart
from .response import Response, build_response
from .settings import CLIENT_IDENTIFIERS, ClientIdentifiers
from .structures import CaseInsensitiveDict

# Request body: str and bytes are sent as-is, a mapping or a list of (name, value) pairs is form-encoded.
_Data: TypeAlias = str | bytes | Mapping[str, Any] | list[tuple[str, Any]]
# JSON body: dicts and lists are serialized, a str is sent as-is.
_Json: TypeAlias = dict[str, Any] | list[Any] | str
# Either a proxy URL, or a dict whose "http" entry is used, or its "https" entry if it has no "http" one.
_Proxy: TypeAlias = dict[str, str] | str

# Statuses followed with allow_redirects, if the response has a Location header
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
# Redirects followed for one request before TooManyRedirects is raised, the same limit as in requests
MAX_REDIRECTS = 30
_DEFAULT_PORTS = {"http": 80, "https": 443}


def _redirect_method(status_code: int, method: str) -> str:
    """Method of the request that follows a redirect, as browsers pick it: 303 turns anything but HEAD into a GET, and
    301 and 302 turn a POST into one. 307 and 308 keep the method."""
    if status_code == 303 and method.upper() != "HEAD":
        return "GET"
    if status_code in (301, 302) and method.upper() == "POST":
        return "GET"
    return method


def _leaves_origin(url: str, next_url: str) -> bool:
    """Whether a redirect from url to next_url changes host, port or scheme. An upgrade from http to https on the
    default ports doesn't count, like in requests."""
    old, new = urllib.parse.urlsplit(url), urllib.parse.urlsplit(next_url)
    if old.hostname != new.hostname:
        return True
    old_port = old.port or _DEFAULT_PORTS.get(old.scheme)
    new_port = new.port or _DEFAULT_PORTS.get(new.scheme)
    if old.scheme == "http" and old_port == 80 and new.scheme == "https" and new_port == 443:
        return False
    return old.scheme != new.scheme or old_port != new_port


class Session:
    def __init__(
        self,
        client_identifier: ClientIdentifiers | None = "chrome_120",
        ja3_string: str | None = None,
        h2_settings: dict[str, int] | None = None,
        h2_settings_order: list[str] | None = None,
        supported_signature_algorithms: list[str] | None = None,
        supported_delegated_credentials_algorithms: list[str] | None = None,
        supported_versions: list[str] | None = None,
        key_share_curves: list[str] | None = None,
        cert_compression_algo: str | None = None,
        additional_decode: str | None = None,
        pseudo_header_order: list[str] | None = None,
        connection_flow: int | None = None,
        priority_frames: list[dict[str, Any]] | None = None,
        header_order: list[str] | None = None,
        header_priority: dict[str, Any] | None = None,
        random_tls_extension_order: bool = False,
        force_http1: bool = False,
        catch_panics: bool = False,
        debug: bool = False,
        certificate_pinning: dict[str, list[str]] | None = None,
        alpn_protocols: list[str] | None = None,
        alps_protocols: list[str] | None = None,
    ) -> None:
        # The library silently falls back to its default profile for unknown names, so catch typos here instead.
        if client_identifier is not None and client_identifier not in CLIENT_IDENTIFIERS:
            by_lowercase = {name.lower(): name for name in CLIENT_IDENTIFIERS}
            matches = difflib.get_close_matches(str(client_identifier).lower(), by_lowercase, n=3)
            hint = f" Did you mean {', '.join(repr(by_lowercase[m]) for m in matches)}?" if matches else ""
            raise ValueError(
                f"Unknown client_identifier {client_identifier!r}.{hint} Every supported name is listed in "
                "tls_client/settings.py; pass client_identifier=None to use a custom TLS configuration instead."
            )

        self._session_id = str(uuid.uuid4())
        # The library sets a native session's timeout and certificate verification when the session sends its first
        # request and keeps them. So each combination of the two gets a native session of its own, whose ID is made
        # from self._session_id and the two values. These are the IDs sent so far, which close() destroys.
        self._native_session_ids: set[str] = set()
        # --- Standard Settings ----------------------------------------------------------------------------------------

        # Case-insensitive dictionary of headers, send on each request
        self.headers: CaseInsensitiveDict[str] = CaseInsensitiveDict(
            {
                "User-Agent": f"tls-client/{__version__}",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept": "*/*",
                "Connection": "keep-alive",
            }
        )

        # Example:
        # {
        #     "http": "http://user:pass@ip:port",
        #     "https": "http://user:pass@ip:port"
        # }
        self.proxies: _Proxy = {}

        # Dictionary of querystring data to attach to each request. The dictionary values may be lists for representing
        # multivalued query parameters.
        self.params: dict[str, Any] = {}

        # CookieJar containing all currently outstanding cookies set on this session
        self.cookies = cookiejar_from_dict({})

        # Timeout in seconds (int or float) for requests that don't pass timeout
        self.timeout_seconds: float = 30

        # Certificate pinning
        self.certificate_pinning = certificate_pinning

        # --- Advanced Settings ----------------------------------------------------------------------------------------

        # Browser profile to impersonate, e.g. chrome_120, firefox_120 or safari_ios_17_0.
        # For all possible client identifiers, check out the settings.py.
        # None uses the custom TLS settings below (ja3_string, h2_settings, ...) instead of a preset.
        self.client_identifier = client_identifier

        # Set JA3 --> TLSVersion, Ciphers, Extensions, EllipticCurves, EllipticCurvePointFormats
        # Example:
        # 771,4865-4866-4867-49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53,0-23-65281-10-11-35-16-5-13-18-51-45-43-27-17513,29-23-24,0
        self.ja3_string = ja3_string

        # HTTP2 Header Frame Settings
        # Possible Settings:
        # HEADER_TABLE_SIZE
        # SETTINGS_ENABLE_PUSH
        # MAX_CONCURRENT_STREAMS
        # INITIAL_WINDOW_SIZE
        # MAX_FRAME_SIZE
        # MAX_HEADER_LIST_SIZE
        #
        # Example:
        # {
        #     "HEADER_TABLE_SIZE": 65536,
        #     "MAX_CONCURRENT_STREAMS": 1000,
        #     "INITIAL_WINDOW_SIZE": 6291456,
        #     "MAX_HEADER_LIST_SIZE": 262144
        # }
        self.h2_settings = h2_settings

        # HTTP2 Header Frame Settings Order
        # Example:
        # [
        #     "HEADER_TABLE_SIZE",
        #     "MAX_CONCURRENT_STREAMS",
        #     "INITIAL_WINDOW_SIZE",
        #     "MAX_HEADER_LIST_SIZE"
        # ]
        self.h2_settings_order = h2_settings_order

        # Supported Signature Algorithms
        # Possible Settings:
        # PKCS1WithSHA256
        # PKCS1WithSHA384
        # PKCS1WithSHA512
        # PSSWithSHA256
        # PSSWithSHA384
        # PSSWithSHA512
        # ECDSAWithP256AndSHA256
        # ECDSAWithP384AndSHA384
        # ECDSAWithP521AndSHA512
        # PKCS1WithSHA1
        # ECDSAWithSHA1
        #
        # Example:
        # [
        #     "ECDSAWithP256AndSHA256",
        #     "PSSWithSHA256",
        #     "PKCS1WithSHA256",
        #     "ECDSAWithP384AndSHA384",
        #     "PSSWithSHA384",
        #     "PKCS1WithSHA384",
        #     "PSSWithSHA512",
        #     "PKCS1WithSHA512",
        # ]
        self.supported_signature_algorithms = supported_signature_algorithms

        # Supported Delegated Credentials Algorithms
        # Possible Settings:
        # PKCS1WithSHA256
        # PKCS1WithSHA384
        # PKCS1WithSHA512
        # PSSWithSHA256
        # PSSWithSHA384
        # PSSWithSHA512
        # ECDSAWithP256AndSHA256
        # ECDSAWithP384AndSHA384
        # ECDSAWithP521AndSHA512
        # PKCS1WithSHA1
        # ECDSAWithSHA1
        #
        # Example:
        # [
        #     "ECDSAWithP256AndSHA256",
        #     "PSSWithSHA256",
        #     "PKCS1WithSHA256",
        #     "ECDSAWithP384AndSHA384",
        #     "PSSWithSHA384",
        #     "PKCS1WithSHA384",
        #     "PSSWithSHA512",
        #     "PKCS1WithSHA512",
        # ]
        self.supported_delegated_credentials_algorithms = supported_delegated_credentials_algorithms

        # Supported Versions
        # Possible Settings:
        # GREASE
        # 1.3
        # 1.2
        # 1.1
        # 1.0
        #
        # Example:
        # [
        #     "GREASE",
        #     "1.3",
        #     "1.2"
        # ]
        self.supported_versions = supported_versions

        # Key Share Curves
        # Possible Settings:
        # GREASE
        # P256
        # P384
        # P521
        # X25519
        #
        # Example:
        # [
        #     "GREASE",
        #     "X25519"
        # ]
        self.key_share_curves = key_share_curves

        # Cert Compression Algorithm
        # Examples: "zlib", "brotli", "zstd"
        self.cert_compression_algo = cert_compression_algo

        # ALPN Protocols, sent in the application_layer_protocol_negotiation extension (16) of the JA3
        # Defaults to h2 and http/1.1 like the presets. Servers abort the handshake if the extension is sent empty.
        # Example:
        # [
        #     "h2",
        #     "http/1.1"
        # ]
        self.alpn_protocols = ["h2", "http/1.1"] if alpn_protocols is None else alpn_protocols

        # ALPS Protocols, sent in the application_settings extension (17513 or 17613) of the JA3
        # Example:
        # [
        #     "h2"
        # ]
        self.alps_protocols = alps_protocols

        # Additional Decode
        # Make sure the go code decodes the response body once explicit by provided algorithm.
        # Examples: null, "gzip", "br", "deflate"
        self.additional_decode = additional_decode

        # Pseudo Header Order (:authority, :method, :path, :scheme)
        # Example:
        # [
        #     ":method",
        #     ":authority",
        #     ":scheme",
        #     ":path"
        # ]
        self.pseudo_header_order = pseudo_header_order

        # Connection Flow / Window Size Increment
        # Example:
        # 15663105
        self.connection_flow = connection_flow

        # Example:
        # [
        #   {
        #     "streamID": 3,
        #     "priorityParam": {
        #       "weight": 201,
        #       "streamDep": 0,
        #       "exclusive": false
        #     }
        #   },
        #   {
        #     "streamID": 5,
        #     "priorityParam": {
        #       "weight": 101,
        #       "streamDep": false,
        #       "exclusive": 0
        #     }
        #   }
        # ]
        self.priority_frames = priority_frames

        # Order of your headers
        # Example:
        # [
        #   "key1",
        #   "key2"
        # ]
        self.header_order = header_order

        # Header Priority
        # Example:
        # {
        #   "streamDep": 1,
        #   "exclusive": true,
        #   "weight": 1
        # }
        self.header_priority = header_priority

        # randomize tls extension order
        self.random_tls_extension_order = random_tls_extension_order

        # force HTTP1
        self.force_http1 = force_http1

        # catch panics
        # avoid the tls client to print the whole stacktrace when a panic (critical go error) happens
        self.catch_panics = catch_panics

        # debugging
        self.debug = debug

    def __enter__(self) -> "Session":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> str:
        """Destroys the native sessions of this session and returns the library's reply for the last one."""
        destroy_session_response_string = ""
        for session_id in sorted(self._native_session_ids) or [self._session_id]:
            destroy_session_payload = {"sessionId": session_id}

            destroy_session_response = destroySession(dumps(destroy_session_payload).encode("utf-8"))
            # we dereference the pointer to a byte array
            destroy_session_response_bytes = ctypes.string_at(destroy_session_response)
            # convert our byte array to a string (tls client returns json)
            destroy_session_response_string = destroy_session_response_bytes.decode("utf-8")
            # convert response string to json
            destroy_session_response_object = loads(destroy_session_response_string)

            freeMemory(destroy_session_response_object["id"].encode("utf-8"))

        return destroy_session_response_string

    def execute_request(
        self,
        method: str,
        url: str,
        params: Mapping[str, Any] | None = None,
        data: _Data | None = None,
        headers: Mapping[str, str | None] | None = None,
        header_order: list[str] | None = None,
        cookies: dict[str, str] | CookieJar | None = None,
        json: _Json | None = None,
        allow_redirects: bool = False,
        insecure_skip_verify: bool = False,
        timeout_seconds: float | None = None,
        proxy: _Proxy | None = None,
        timeout: float | None = None,
        files: Files | None = None,
    ) -> Response:
        """Sends a request and returns its Response.

        params are added to the query string after self.params, and after any query the URL already has.

        timeout is how many seconds (int or float) to wait for the response, like in requests. timeout_seconds is
        the older name for it; passing both raises ValueError. Without either, self.timeout_seconds applies.
        """
        # --- URL ------------------------------------------------------------------------------------------------------
        # Prepare URL - add params to url. A parameter passed in replaces the session parameter of the same name.
        query = urllib.parse.urlencode({**self.params, **(params or {})}, doseq=True)
        if query:
            parts = urllib.parse.urlsplit(url)
            url = urllib.parse.urlunsplit(parts._replace(query=f"{parts.query}&{query}" if parts.query else query))

        # --- Request Body ---------------------------------------------------------------------------------------------
        # Prepare request body - build request body
        # Files are sent as multipart/form-data, with the fields of data before them.
        # Otherwise data has priority. JSON is only used if data is None.
        request_body: str | bytes | None
        content_type: str | None
        if files:
            if json is not None:
                raise ValueError("files can't be sent with json; pass the other form fields in data instead")
            if isinstance(data, (str, bytes)):
                raise ValueError("files can't be sent with str or bytes data; pass the form fields as a dict instead")
            request_body, content_type = encode_multipart(data, files)
        elif data is None and json is not None:
            request_body = dumps(json) if isinstance(json, (dict, list)) else json
            content_type = "application/json"
        elif data is None or isinstance(data, (str, bytes)):
            request_body = data
            content_type = None
        else:
            request_body = urllib.parse.urlencode(data, doseq=True)
            content_type = "application/x-www-form-urlencoded"
        # --- Headers --------------------------------------------------------------------------------------------------
        # Merge into a copy, so nothing set for this request sticks to self.headers.
        request_headers: CaseInsensitiveDict[str | None] = CaseInsensitiveDict(self.headers)
        if headers is not None:
            request_headers.update(headers)

        # set content type if neither the session nor the request set one (setting it to None sends none)
        if content_type is not None and "content-type" not in request_headers:
            request_headers["Content-Type"] = content_type

        # Remove items, where the key or value is set to None.
        none_keys = [k for (k, v) in request_headers.items() if v is None or k is None]
        for key in none_keys:
            del request_headers[key]

        # Ability to overwrite self.header_order for flexibility
        request_header_order = self.header_order
        if header_order:
            request_header_order = header_order

        # --- Cookies --------------------------------------------------------------------------------------------------
        # Request cookies are added to the session jar. The jar is the only cookie store: the library runs without one
        # (withoutCookieJar), so a cookie removed from the jar is no longer sent.
        cookie_jar = merge_cookies(self.cookies, cookies or {})
        # The jar's cookies are added to each request, redirects included, as a Cookie header. A Cookie header passed in
        # is sent before them.
        passed_cookie_header = request_headers.pop("Cookie", None)

        # --- Proxy ----------------------------------------------------------------------------------------------------
        proxy = proxy or self.proxies

        if isinstance(proxy, dict):
            # The "http" entry is used for every URL, https ones included
            proxy_url = proxy.get("http") or proxy.get("https") or ""
        elif isinstance(proxy, str):
            proxy_url = proxy
        else:
            proxy_url = ""

        # --- Timeout --------------------------------------------------------------------------------------------------
        # maximum time to wait for a response. timeout is the requests-style name for timeout_seconds.
        if timeout is not None and timeout_seconds is not None:
            raise ValueError("Pass either timeout or timeout_seconds, not both")

        request_timeout = timeout or timeout_seconds or self.timeout_seconds
        timeout_milliseconds = round(request_timeout * 1000)

        # The native session for this timeout and certificate verification, see self._native_session_ids
        session_id = f"{self._session_id}-{timeout_milliseconds}ms{'-insecure' if insecure_skip_verify else ''}"
        self._native_session_ids.add(session_id)

        # --- Certificate pinning --------------------------------------------------------------------------------------
        # pins a certificate so that it restricts which certificates are considered valid

        certificate_pinning = self.certificate_pinning

        # --- Request --------------------------------------------------------------------------------------------------
        # Settings shared by every request of a redirect chain. The URL, method, headers and body are set per request.
        request_payload: dict[str, Any] = {
            "sessionId": session_id,
            # Redirects are followed below, so that the cookies set on every hop end up in self.cookies.
            "followRedirects": False,
            # Cookies come from self.cookies only. Without this, the library also keeps the cookies of every response
            # in a jar of its own and sends them on later requests of the session.
            "withoutCookieJar": True,
            "forceHttp1": self.force_http1,
            "withDebug": self.debug,
            "catchPanics": self.catch_panics,
            "headerOrder": request_header_order,
            "insecureSkipVerify": insecure_skip_verify,
            # Return the body as base64 so binary bodies survive; build_response decodes it.
            "isByteResponse": True,
            "additionalDecode": self.additional_decode,
            "proxyUrl": proxy_url,
            # Milliseconds, so fractions of a second work. The library rejects timeoutSeconds alongside it.
            "timeoutMilliseconds": timeout_milliseconds,
        }
        if certificate_pinning:
            request_payload["certificatePinningHosts"] = certificate_pinning
        if self.client_identifier is None:
            request_payload["customTlsClient"] = {
                "ja3String": self.ja3_string,
                "h2Settings": self.h2_settings,
                "h2SettingsOrder": self.h2_settings_order,
                "pseudoHeaderOrder": self.pseudo_header_order,
                "connectionFlow": self.connection_flow,
                "priorityFrames": self.priority_frames,
                "headerPriority": self.header_priority,
                "certCompressionAlgos": [self.cert_compression_algo] if self.cert_compression_algo else None,
                "supportedVersions": self.supported_versions,
                "supportedSignatureAlgorithms": self.supported_signature_algorithms,
                "supportedDelegatedCredentialsAlgorithms": self.supported_delegated_credentials_algorithms,
                "keyShareCurves": self.key_share_curves,
                "alpnProtocols": self.alpn_protocols,
                "alpsProtocols": self.alps_protocols,
            }
        else:
            request_payload["tlsClientIdentifier"] = self.client_identifier
            request_payload["withRandomTLSExtensionOrder"] = self.random_tls_extension_order

        # Sends the request, then with allow_redirects each request a redirect asks for, like requests does.
        history: list[Response] = []
        # Cookies set on any hop of a redirect chain, for the final response
        chain_cookies = cookiejar_from_dict({})
        while True:
            # The jar picks the cookies for the URL by domain, path, secure flag and expiry.
            sent_headers = CaseInsensitiveDict(request_headers)
            cookie_header = "; ".join(
                filter(None, [passed_cookie_header, get_cookie_header(cookie_jar, url, request_headers)])
            )
            if cookie_header:
                sent_headers["Cookie"] = cookie_header
            request_payload["headers"] = dict(sent_headers)
            request_payload["requestUrl"] = url
            request_payload["requestMethod"] = method
            request_payload["isByteRequest"] = isinstance(request_body, (bytes, bytearray))
            request_payload["requestBody"] = (
                base64.b64encode(request_body).decode()
                if isinstance(request_body, (bytes, bytearray))
                else request_body
            )

            # dereference the pointer to the response, decode it and parse it (tls client returns json). None of the
            # steps is bound to a name, so each copy of a large reply is freed as soon as the next one exists.
            response_object = loads(ctypes.string_at(request(dumps(request_payload).encode("utf-8"))).decode("utf-8"))
            # free the memory
            freeMemory(response_object["id"].encode("utf-8"))
            # --- Response ---------------------------------------------------------------------------------------------
            # Error handling
            if response_object["status"] == 0:
                raise TLSClientException(response_object["body"])
            # Set response cookies
            response_cookie_jar = extract_cookies_to_jar(
                request_url=url,
                request_headers=request_headers,
                cookie_jar=cookie_jar,
                response_headers=response_object["headers"],
            )
            chain_cookies.update(response_cookie_jar)
            # build response class
            response = build_response(response_object, response_cookie_jar)

            # --- Redirects --------------------------------------------------------------------------------------------
            location = response.headers.get("Location")
            if not allow_redirects or response.status_code not in _REDIRECT_STATUSES or location is None:
                break
            if len(history) == MAX_REDIRECTS:
                raise TooManyRedirects(f"Exceeded {MAX_REDIRECTS} redirects, the last from {url}")
            history.append(response)

            # A relative Location is resolved against the current URL. Like in requests, the fragment carries over
            # unless the Location has one of its own.
            next_url = urllib.parse.urljoin(url, location if isinstance(location, str) else location[0])
            fragment = urllib.parse.urlsplit(url).fragment
            if fragment and not urllib.parse.urlsplit(next_url).fragment:
                next_url = f"{next_url}#{fragment}"
            # Credentials passed for one host aren't sent to another
            if _leaves_origin(url, next_url):
                request_headers.pop("Authorization", None)
                passed_cookie_header = None
            url = next_url

            next_method = _redirect_method(response.status_code, method)
            if next_method != method:
                # The request turned into a GET, which has no body
                method = next_method
                request_body = None
                for header in ("Content-Type", "Content-Length", "Transfer-Encoding"):
                    request_headers.pop(header, None)

        response.history = history
        response.cookies = chain_cookies
        return response

    def get(self, url: str, **kwargs: Any) -> Response:
        """Sends a GET request"""
        return self.execute_request(method="GET", url=url, **kwargs)

    def options(self, url: str, **kwargs: Any) -> Response:
        """Sends a OPTIONS request"""
        return self.execute_request(method="OPTIONS", url=url, **kwargs)

    def head(self, url: str, **kwargs: Any) -> Response:
        """Sends a HEAD request"""
        return self.execute_request(method="HEAD", url=url, **kwargs)

    def post(
        self,
        url: str,
        data: _Data | None = None,
        json: _Json | None = None,
        files: Files | None = None,
        **kwargs: Any,
    ) -> Response:
        """Sends a POST request"""
        return self.execute_request(method="POST", url=url, data=data, json=json, files=files, **kwargs)

    def put(
        self,
        url: str,
        data: _Data | None = None,
        json: _Json | None = None,
        files: Files | None = None,
        **kwargs: Any,
    ) -> Response:
        """Sends a PUT request"""
        return self.execute_request(method="PUT", url=url, data=data, json=json, files=files, **kwargs)

    def patch(
        self,
        url: str,
        data: _Data | None = None,
        json: _Json | None = None,
        files: Files | None = None,
        **kwargs: Any,
    ) -> Response:
        """Sends a PATCH request"""
        return self.execute_request(method="PATCH", url=url, data=data, json=json, files=files, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> Response:
        """Sends a DELETE request"""
        return self.execute_request(method="DELETE", url=url, **kwargs)
