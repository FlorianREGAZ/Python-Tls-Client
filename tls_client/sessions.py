from .cffi import request, freeMemory, destroySession
from .cookies import cookiejar_from_dict, merge_cookies, extract_cookies_to_jar
from .exceptions import TLSClientExeption
from .response import build_response, Response
from .settings import ClientIdentifiers
from .structures import CaseInsensitiveDict
from .__version__ import __version__

from typing import Any, Dict, List, Optional, Union
from json import dumps, loads
import urllib.parse
import base64
import ctypes
import uuid


class Session:

    def __init__(
        self,
        client_identifier: ClientIdentifiers = "chrome_120",
        ja3_string: Optional[str] = None,
        h2_settings: Optional[Dict[str, int]] = None,
        h2_settings_order: Optional[List[str]] = None,
        supported_signature_algorithms: Optional[List[str]] = None,
        supported_delegated_credentials_algorithms: Optional[List[str]] = None,
        supported_versions: Optional[List[str]] = None,
        key_share_curves: Optional[List[str]] = None,
        cert_compression_algo: str = None,
        additional_decode: str = None,
        pseudo_header_order: Optional[List[str]] = None,
        connection_flow: Optional[int] = None,
        priority_frames: Optional[list] = None,
        header_order: Optional[List[str]] = None,
        header_priority: Optional[List[str]] = None,
        random_tls_extension_order: Optional = False,
        force_http1: Optional = False,
        catch_panics: Optional = False,
        debug: Optional = False,
        certificate_pinning: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        self._session_id = str(uuid.uuid4())
        # --- Standard Settings ----------------------------------------------------------------------------------------

        # Case-insensitive dictionary of headers, send on each request
        self.headers = CaseInsensitiveDict(
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
        self.proxies = {}

        # Dictionary of querystring data to attach to each request. The dictionary values may be lists for representing
        # multivalued query parameters.
        self.params = {}

        # CookieJar containing all currently outstanding cookies set on this session
        self.cookies = cookiejar_from_dict({})

        # Timeout
        self.timeout_seconds = 30

        # Certificate pinning
        self.certificate_pinning = certificate_pinning

        # --- Advanced Settings ----------------------------------------------------------------------------------------

        # Examples:
        # Chrome --> chrome_103, chrome_104, chrome_105, chrome_106
        # Firefox --> firefox_102, firefox_104
        # Opera --> opera_89, opera_90
        # Safari --> safari_15_3, safari_15_6_1, safari_16_0
        # iOS --> safari_ios_15_5, safari_ios_15_6, safari_ios_16_0
        # iPadOS --> safari_ios_15_6
        #
        # for all possible client identifiers, check out the settings.py
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

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self) -> str:
        destroy_session_payload = {
            "sessionId": self._session_id
        }

        destroy_session_response = destroySession(dumps(destroy_session_payload).encode('utf-8'))
        # we dereference the pointer to a byte array
        destroy_session_response_bytes = ctypes.string_at(destroy_session_response)
        # convert our byte array to a string (tls client returns json)
        destroy_session_response_string = destroy_session_response_bytes.decode('utf-8')
        # convert response string to json
        destroy_session_response_object = loads(destroy_session_response_string)

        freeMemory(destroy_session_response_object['id'].encode('utf-8'))

        return destroy_session_response_string

    def execute_request(
        self,
        method: str,
        url: str,
        params: Optional[dict] = None,  # Optional[dict[str, str]]
        data: Optional[Union[str, dict]] = None,
        headers: Optional[dict] = None,  # Optional[dict[str, str]]
        cookies: Optional[dict] = None,  # Optional[dict[str, str]]
        json: Optional[dict] = None,  # Optional[dict]
        allow_redirects: Optional[bool] = False,
        insecure_skip_verify: Optional[bool] = False,
        timeout_seconds: Optional[int] = None,
        proxy: Optional[dict] = None  # Optional[dict[str, str]]
    ) -> Response:
        # --- URL ------------------------------------------------------------------------------------------------------
        # Prepare URL - add params to url
        if params is not None:
            url = f"{url}?{urllib.parse.urlencode(params, doseq=True)}"
        if headers is None: headers = {}
        # --- Request Body ---------------------------------------------------------------------------------------------
        # Prepare request body - build request body
        # Data has priority. JSON is only used if data is None.
        if data is None and json is not None:
            if type(json) in [dict, list]:
                json = dumps(json)
            request_body = json
            content_type = "application/json"
        elif data is not None and type(data) not in [str, bytes]:
            request_body = urllib.parse.urlencode(data, doseq=True)
            content_type = "application/x-www-form-urlencoded"
        else:
            request_body = data
            content_type = None
        # set content type if it isn't set
        if content_type is not None and "content-type" not in self.headers:
            headers["Content-Type"] = content_type

        # --- Headers --------------------------------------------------------------------------------------------------
        if self.headers is None:
            headers = CaseInsensitiveDict(headers)
        elif headers is None:
            headers = self.headers
        else:
            merged_headers = CaseInsensitiveDict(self.headers)
            merged_headers.update(headers)

            # Remove items, where the key or value is set to None.
            none_keys = [k for (k, v) in merged_headers.items() if v is None or k is None]
            for key in none_keys:
                del merged_headers[key]

            headers = merged_headers

        # --- Cookies --------------------------------------------------------------------------------------------------
        cookies = cookies or {}
        # Merge with session cookies
        cookies = merge_cookies(self.cookies, cookies)
        # turn cookie jar into dict
        # in the cookie value the " gets removed, because the fhttp library in golang doesn't accept the character
        request_cookies = [
            {'domain': c.domain, 'expires': c.expires, 'name': c.name, 'path': c.path, 'value': c.value.replace('"', "")}
            for c in cookies
        ]

        # --- Proxy ----------------------------------------------------------------------------------------------------
        proxy = proxy or self.proxies
        
        if type(proxy) is dict and "http" in proxy:
            proxy = proxy["http"]
        elif type(proxy) is str:
            proxy = proxy
        else:
            proxy = ""

        # --- Timeout --------------------------------------------------------------------------------------------------
        # maximum time to wait for a response

        timeout_seconds = timeout_seconds or self.timeout_seconds

        # --- Certificate pinning --------------------------------------------------------------------------------------
        # pins a certificate so that it restricts which certificates are considered valid

        certificate_pinning = self.certificate_pinning
        
        # --- Request --------------------------------------------------------------------------------------------------
        is_byte_request = isinstance(request_body, (bytes, bytearray))
        request_payload = {
            "sessionId": self._session_id,
            "followRedirects": allow_redirects,
            "forceHttp1": self.force_http1,
            "withDebug": self.debug,
            "catchPanics": self.catch_panics,
            "headers": dict(headers),
            "headerOrder": self.header_order,
            "insecureSkipVerify": insecure_skip_verify,
            "isByteRequest": is_byte_request,
            "additionalDecode": self.additional_decode,
            "proxyUrl": proxy,
            "requestUrl": url,
            "requestMethod": method,
            "requestBody": base64.b64encode(request_body).decode() if is_byte_request else request_body,
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
                "certCompressionAlgo": self.cert_compression_algo,
                "supportedVersions": self.supported_versions,
                "supportedSignatureAlgorithms": self.supported_signature_algorithms,
                "supportedDelegatedCredentialsAlgorithms": self.supported_delegated_credentials_algorithms ,
                "keyShareCurves": self.key_share_curves,
            }
        else:
            request_payload["tlsClientIdentifier"] = self.client_identifier
            request_payload["withRandomTLSExtensionOrder"] = self.random_tls_extension_order

        # this is a pointer to the response
        response = request(dumps(request_payload).encode('utf-8'))
        # dereference the pointer to a byte array
        response_bytes = ctypes.string_at(response)
        # convert our byte array to a string (tls client returns json)
        response_string = response_bytes.decode('utf-8')
        # convert response string to json
        response_object = loads(response_string)
        # free the memory
        freeMemory(response_object['id'].encode('utf-8'))
        # --- Response -------------------------------------------------------------------------------------------------
        # Error handling
        if response_object["status"] == 0:
            raise TLSClientExeption(response_object["body"])
        # Set response cookies
        response_cookie_jar = extract_cookies_to_jar(
            request_url=url,
            request_headers=headers,
            cookie_jar=cookies,
            response_headers=response_object["headers"]
        )
        # build response class
        return build_response(response_object, response_cookie_jar)

    def get(
        self,
        url: str,
        **kwargs: Any
    ) -> Response:
        """Sends a GET request"""
        return self.execute_request(method="GET", url=url, **kwargs)

    def options(
        self,
        url: str,
        **kwargs: Any
    ) -> Response:
        """Sends a OPTIONS request"""
        return self.execute_request(method="OPTIONS", url=url, **kwargs)

    def head(
        self,
        url: str,
        **kwargs: Any
    ) -> Response:
        """Sends a HEAD request"""
        return self.execute_request(method="HEAD", url=url, **kwargs)

    def post(
        self,
        url: str,
        data: Optional[Union[str, dict]] = None,
        json: Optional[dict] = None,
        **kwargs: Any
    ) -> Response:
        """Sends a POST request"""
        return self.execute_request(method="POST", url=url, data=data, json=json, **kwargs)

    def put(
        self,
        url: str,
        data: Optional[Union[str, dict]] = None,
        json: Optional[dict] = None,
        **kwargs: Any
    ) -> Response:
        """Sends a PUT request"""
        return self.execute_request(method="PUT", url=url, data=data, json=json, **kwargs)

    def patch(
        self,
        url: str,
        data: Optional[Union[str, dict]] = None,
        json: Optional[dict] = None,
        **kwargs: Any
    ) -> Response:
        """Sends a PATCH request"""
        return self.execute_request(method="PATCH", url=url, data=data, json=json, **kwargs)

    def delete(
        self,
        url: str,
        **kwargs: Any
    ) -> Response:
        """Sends a DELETE request"""
        return self.execute_request(method="DELETE", url=url, **kwargs)
