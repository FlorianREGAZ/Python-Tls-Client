from .cffi import request
from .cookies import cookiejar_from_dict, get_cookie_header, merge_cookies
from .structures import CaseInsensitiveDict
from .__version__ import __version__

from http.cookiejar import CookieJar
from typing import Optional, Union
from json import dumps, loads
import urllib.parse
import ctypes


class Session:

    def __init__(
        self,
        client_identifier: Optional[str] = None,
        ja3_string: Optional[str] = None,
        h2_settings: Optional[dict[int, int]] = None,
        h2_settings_order: Optional[list[int]] = None,
        pseudo_header_order: Optional[list[str]] = None,
        connection_flow: Optional[int] = None,
        priority_frames: Optional[str] = None,
        header_order: Optional[list[str]] = None,
    ) -> None:
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

        # --- Advanced Settings ----------------------------------------------------------------------------------------

        # Examples:
        # Chrome --> chrome_103, chrome_104, chrome_105
        # Firefox --> firefox_102, firefox_104
        # Opera --> opera_89, opera_90
        # Safari --> safari_15_3, safari_15_6_1, safari_16_0
        # iOS --> safari_ios_15_5, safari_ios_15_6, safari_ios_16_0
        # iPadOS --> safari_ios_15_6
        self.client_identifier = client_identifier

        # Set JA3 --> TLSVersion, Ciphers, Extensions, EllipticCurves, EllipticCurvePointFormats
        # Example:
        # 771,4865-4866-4867-49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53,0-23-65281-10-11-35-16-5-13-18-51-45-43-27-17513,29-23-24,0
        self.ja3_string = ja3_string

        # HTTP2 Header Frame Settings
        # Example:
        # {
        #   1: 65536,
        #   3: 1000,
        #   4: 6291456,
        #   6: 262144
        # }
        # 1 = HEADER_TABLE_SIZE
        # 2 = SETTINGS_ENABLE_PUSH
        # 3 = MAX_CONCURRENT_STREAMS
        # 4 = INITIAL_WINDOW_SIZE
        # 5 = MAX_FRAME_SIZE
        # 6 = MAX_HEADER_LIST_SIZE
        self.h2_settings = h2_settings

        # HTTP2 Header Frame Settings Order
        # Example:
        # [
        #     1,
        #     3,
        #     4,
        #     6
        # ]
        self.h2_settings_order = h2_settings_order

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

        # TODO
        self.priority_frames = priority_frames

        # Order of your headers
        # Example:
        # [
        #   "key1",
        #   "key2"
        # ]
        self.header_order = header_order

    def execute_request(
        self,
        method: str,
        url: str,
        params: Optional[dict[str, str]] = None,
        data: Optional[Union[str, dict]] = None,
        headers: Optional[dict[str, str]] = None,
        cookies: Optional[dict[str, str]] = None,
        json: Optional[dict] = None,
        allow_redirects: Optional[bool] = False,
        insecure_skip_verify: Optional[bool] = False,
        timeout_seconds: Optional[int] = 30,
        proxies: Optional[dict[str, str]] = None
    ):
        # --- URL ------------------------------------------------------------------------------------------------------
        # Prepare URL - add params to url
        if params is not None:
            url = f"{url}?{urllib.parse.urlencode(params, doseq=True)}"

        # --- Request Body ---------------------------------------------------------------------------------------------
        # Prepare request body - build request body
        # Data has priority. JSON is only used if data is None.
        if data is None and json is not None:
            if type(json) in [dict, list]:
                json = dumps(json)
            request_body = json
            content_type = "application/json"
        elif type(data) not in [str, bytes]:
            request_body = urllib.parse.urlencode(data, doseq=True)
            content_type = "application/x-www-form-urlencoded"
        else:
            request_body = data
            content_type = None
        # set content type if it isn't set
        if content_type is not None and "content-type" not in self.headers:
            self.headers["Content-Type"] = content_type

        # --- Headers --------------------------------------------------------------------------------------------------
        # merge headers of session and of the request
        if headers is not None:
            for header_key, header_value in headers.items():
                # check if all header keys and values are strings
                if type(header_key) is str and type(header_value) is str:
                    self.headers[header_key] = header_value
        else:
            headers = self.headers

        # set content length header
        if method not in ["GET", "HEAD"] and request_body is not None:
            headers["Content-Length"] = str(len(request_body))
        elif method not in ["GET", "HEAD"] and request_body is None:
            headers["Content-Length"] = "0"
        # --- Cookies --------------------------------------------------------------------------------------------------
        cookies = request.cookies or {}
        # Merge with session cookies
        cookies = merge_cookies(self.cookies, cookies)

        cookie_header = get_cookie_header(
            request_url=url,
            request_headers=headers,
            cookie_jar=cookies
        )
        if cookie_header is not None:
            self.headers["Cookie"] = cookie_header

        # --- Proxy ----------------------------------------------------------------------------------------------------
        # TODO Prepare proxy - format proxy correctly

        # --- Request --------------------------------------------------------------------------------------------------
        request_payload = {
            "proxyUrl": "",  # TODO
            "followRedirects": allow_redirects,
            "insecureSkipVerify": insecure_skip_verify,
            "timeoutSeconds": timeout_seconds,
            "headers": headers,
            "headerOrder": self.header_order,
            "requestUrl": url,
            "requestMethod": method,
            "requestBody": request_body,
            "requestCookies": []  # Empty because its handled in python
        }
        if self.client_identifier is None:
            request_payload["customTlsClient"] = {
                "ja3String": self.ja3_string,
                "h2Settings": self.h2_settings,
                "h2SettingsOrder": self.h2_settings_order,
                "pseudoHeaderOrder": self.pseudo_header_order,
                "connectionFlow": self.connection_flow,
                "priorityFrames": self.priority_frames
            }
        else:
            request_payload["tlsClientIdentifier"] = self.client_identifier

        # this is a pointer to the response
        response = request(dumps(request_payload).encode('utf-8'))
        # dereference the pointer to a byte array
        response_bytes = ctypes.string_at(response)
        # convert our byte array to a string (tls client returns json)
        response_string = response_bytes.decode('utf-8')
        # convert response string to json
        response_object = loads(response_string)  # TODO convert to response class

        # --- Response -------------------------------------------------------------------------------------------------
