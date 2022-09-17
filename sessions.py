from .structures import CaseInsensitiveDict
from .__version__ import __version__

from typing import Optional

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
        # TODO: self.cookies = cookiejar_from_dict({})

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
