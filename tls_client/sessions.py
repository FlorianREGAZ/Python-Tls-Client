from .cffi import request
from .cookies import cookiejar_from_dict, get_cookie_header, merge_cookies, extract_cookies_to_jar
from .exceptions import TLSClientExeption
from .response import build_response
from .structures import CaseInsensitiveDict
from .__version__ import __version__

from typing import Any, Optional, Union
from json import dumps, loads
import urllib.parse
import ctypes
import uuid


class Session:

    def __init__(
        self,
        client_identifier: Optional[str] = None,
        ja3_string: Optional[str] = None,
        h2_settings: Optional[dict] = None,  # Optional[dict[int, int]]
        h2_settings_order: Optional[list] = None, # Optional[list[int]]
        pseudo_header_order: Optional[list] = None,  # Optional[list[str]
        connection_flow: Optional[int] = None,
        priority_frames: Optional[list] = None,
        header_order: Optional[list] = None,  # Optional[list[str]]
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
        timeout_seconds: Optional[int] = 30,
        proxy: Optional[dict] = None  # Optional[dict[str, str]]
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
        elif data is not None and type(data) not in [str, bytes]:
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

        # --- Cookies --------------------------------------------------------------------------------------------------
        cookies = cookies or {}
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
        proxy = proxy or self.proxies
        
        if type(proxy) is dict and "http" in proxy:
            proxy = proxy["http"]
        elif type(proxy) is str:
            proxy = proxy
        else:
            proxy = ""

        # --- Request --------------------------------------------------------------------------------------------------
        request_payload = {
            "sessionId": self._session_id,
            "proxyUrl": proxy,
            "followRedirects": allow_redirects,
            "insecureSkipVerify": insecure_skip_verify,
            "timeoutSeconds": timeout_seconds,
            "headers": dict(headers),
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
        response_object = loads(response_string)

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
    ):
        """Sends a GET request"""
        return self.execute_request(method="GET", url=url, **kwargs)

    def options(
        self,
        url: str,
        **kwargs: Any
    ):
        """Sends a OPTIONS request"""
        return self.execute_request(method="OPTIONS", url=url, **kwargs)

    def head(
        self,
        url: str,
        **kwargs: Any
    ):
        """Sends a HEAD request"""
        return self.execute_request(method="HEAD", url=url, **kwargs)

    def post(
        self,
        url: str,
        data: Optional[Union[str, dict]] = None,
        json: Optional[dict] = None,
        **kwargs: Any
    ):
        """Sends a POST request"""
        return self.execute_request(method="POST", url=url, data=data, json=json, **kwargs)

    def put(
        self,
        url: str,
        data: Optional[Union[str, dict]] = None,
        json: Optional[dict] = None,
        **kwargs: Any
    ):
        """Sends a PUT request"""
        return self.execute_request(method="PUT", url=url, data=data, json=json, **kwargs)

    def patch(
        self,
        url: str,
        data: Optional[Union[str, dict]] = None,
        json: Optional[dict] = None,
        **kwargs: Any
    ):
        """Sends a PUT request"""
        return self.execute_request(method="PATCH", url=url, data=data, json=json, **kwargs)

    def delete(
        self,
        url: str,
        **kwargs: Any
    ):
        """Sends a DELETE request"""
        return self.execute_request(method="DELETE", url=url, **kwargs)