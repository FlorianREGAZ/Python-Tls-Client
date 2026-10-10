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
from .cookies import cookiejar_from_dict, extract_cookies_to_jar, merge_cookies
from .exceptions import TLSClientException
from .response import Response, build_response
from .settings import CLIENT_IDENTIFIERS, ClientIdentifiers
from .structures import CaseInsensitiveDict

# Request body: str and bytes are sent as-is, a mapping is form-encoded.
_Data: TypeAlias = str | bytes | Mapping[str, Any]
# JSON body: dicts and lists are serialized, a str is sent as-is.
_Json: TypeAlias = dict[str, Any] | list[Any] | str
# Either a proxy URL, or a dict whose "http" entry is used.
_Proxy: TypeAlias = dict[str, str] | str


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

        # Timeout
        self.timeout_seconds = 30

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
        destroy_session_payload = {"sessionId": self._session_id}

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
        timeout_seconds: int | None = None,
        proxy: _Proxy | None = None,
    ) -> Response:
        # --- URL ------------------------------------------------------------------------------------------------------
        # Prepare URL - add params to url
        if params is not None:
            url = f"{url}?{urllib.parse.urlencode(params, doseq=True)}"

        # --- Request Body ---------------------------------------------------------------------------------------------
        # Prepare request body - build request body
        # Data has priority. JSON is only used if data is None.
        request_body: str | bytes | None
        content_type: str | None
        if data is None and json is not None:
            request_body = dumps(json) if isinstance(json, (dict, list)) else json
            content_type = "application/json"
        elif data is None or isinstance(data, (str, bytes)):
            request_body = data
            content_type = None
        else:
            request_body = urllib.parse.urlencode(data, doseq=True)
            content_type = "application/x-www-form-urlencoded"
        # set content type if it isn't set
        if content_type is not None and "content-type" not in self.headers:
            self.headers["Content-Type"] = content_type

        # --- Headers --------------------------------------------------------------------------------------------------
        request_headers: Mapping[str, str | None]
        if self.headers is None:
            request_headers = CaseInsensitiveDict(headers)
        elif headers is None:
            request_headers = self.headers
        else:
            merged_headers: CaseInsensitiveDict[str | None] = CaseInsensitiveDict(self.headers)
            merged_headers.update(headers)

            # Remove items, where the key or value is set to None.
            none_keys = [k for (k, v) in merged_headers.items() if v is None or k is None]
            for key in none_keys:
                del merged_headers[key]

            request_headers = merged_headers

        # Ability to overwrite self.header_order for flexibility
        request_header_order = self.header_order
        if header_order:
            request_header_order = header_order

        # --- Cookies --------------------------------------------------------------------------------------------------
        # Merge with session cookies
        cookie_jar = merge_cookies(self.cookies, cookies or {})
        # turn cookie jar into dict
        # in the cookie value the " gets removed, because the fhttp library in golang doesn't accept the character
        # expires is omitted for session cookies, because the tls client parses null as 1970 and drops the cookie
        request_cookies = [
            {
                "domain": c.domain,
                "name": c.name,
                "path": c.path,
                "value": (c.value or "").replace('"', ""),
                **({"expires": c.expires} if c.expires is not None else {}),
            }
            for c in cookie_jar
        ]

        # --- Proxy ----------------------------------------------------------------------------------------------------
        proxy = proxy or self.proxies

        if isinstance(proxy, dict) and "http" in proxy:
            proxy_url = proxy["http"]
        elif isinstance(proxy, str):
            proxy_url = proxy
        else:
            proxy_url = ""

        # --- Timeout --------------------------------------------------------------------------------------------------
        # maximum time to wait for a response

        timeout_seconds = timeout_seconds or self.timeout_seconds

        # --- Certificate pinning --------------------------------------------------------------------------------------
        # pins a certificate so that it restricts which certificates are considered valid

        certificate_pinning = self.certificate_pinning

        # --- Request --------------------------------------------------------------------------------------------------
        is_byte_request = isinstance(request_body, (bytes, bytearray))
        request_payload: dict[str, Any] = {
            "sessionId": self._session_id,
            "followRedirects": allow_redirects,
            "forceHttp1": self.force_http1,
            "withDebug": self.debug,
            "catchPanics": self.catch_panics,
            "headers": dict(request_headers),
            "headerOrder": request_header_order,
            "insecureSkipVerify": insecure_skip_verify,
            "isByteRequest": is_byte_request,
            # Return the body as base64 so binary bodies survive; build_response decodes it.
            "isByteResponse": True,
            "additionalDecode": self.additional_decode,
            "proxyUrl": proxy_url,
            "requestUrl": url,
            "requestMethod": method,
            "requestBody": base64.b64encode(request_body).decode()
            if isinstance(request_body, (bytes, bytearray))
            else request_body,
            "requestCookies": request_cookies,
            "timeoutSeconds": timeout_seconds,
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

        # dereference the pointer to the response, decode it and parse it (tls client returns json). None of the steps
        # is bound to a name, so each copy of a large reply is freed as soon as the next one exists.
        response_object = loads(ctypes.string_at(request(dumps(request_payload).encode("utf-8"))).decode("utf-8"))
        # free the memory
        freeMemory(response_object["id"].encode("utf-8"))
        # --- Response -------------------------------------------------------------------------------------------------
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
        # build response class
        return build_response(response_object, response_cookie_jar)

    def get(self, url: str, **kwargs: Any) -> Response:
        """Sends a GET request"""
        return self.execute_request(method="GET", url=url, **kwargs)

    def options(self, url: str, **kwargs: Any) -> Response:
        """Sends a OPTIONS request"""
        return self.execute_request(method="OPTIONS", url=url, **kwargs)

    def head(self, url: str, **kwargs: Any) -> Response:
        """Sends a HEAD request"""
        return self.execute_request(method="HEAD", url=url, **kwargs)

    def post(self, url: str, data: _Data | None = None, json: _Json | None = None, **kwargs: Any) -> Response:
        """Sends a POST request"""
        return self.execute_request(method="POST", url=url, data=data, json=json, **kwargs)

    def put(self, url: str, data: _Data | None = None, json: _Json | None = None, **kwargs: Any) -> Response:
        """Sends a PUT request"""
        return self.execute_request(method="PUT", url=url, data=data, json=json, **kwargs)

    def patch(self, url: str, data: _Data | None = None, json: _Json | None = None, **kwargs: Any) -> Response:
        """Sends a PATCH request"""
        return self.execute_request(method="PATCH", url=url, data=data, json=json, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> Response:
        """Sends a DELETE request"""
        return self.execute_request(method="DELETE", url=url, **kwargs)
