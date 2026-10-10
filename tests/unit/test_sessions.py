import base64
import json
from collections.abc import Mapping

import pytest

from tls_client import Session
from tls_client.exceptions import TLSClientException

URL = "https://example.com/path"


def header_values(headers: Mapping[str, str], name: str) -> list[str]:
    """Every value sent under `name`, matched case-insensitively, so duplicates would show up."""
    return [value for key, value in headers.items() if key.lower() == name.lower()]


def sent_cookies(payload: dict) -> dict[str, str]:
    return {cookie["name"]: cookie["value"] for cookie in payload["requestCookies"]}


class TestUrl:
    def test_params_are_encoded_into_the_query_string(self, session, fake_lib):
        session.get(URL, params={"q": "a b", "tag": ["x", "y"]})

        assert fake_lib.sent["requestUrl"] == f"{URL}?q=a+b&tag=x&tag=y"

    @pytest.mark.xfail(reason="params are appended after a second '?' instead of extending the existing query")
    def test_params_extend_an_existing_query_string(self, session, fake_lib):
        session.get(f"{URL}?page=2", params={"q": "x"})

        assert fake_lib.sent["requestUrl"] == f"{URL}?page=2&q=x"

    @pytest.mark.xfail(reason="session.params is never read when building a request")
    def test_session_params_are_sent_with_every_request(self, session, fake_lib):
        session.params = {"api_key": "k"}

        session.get(URL)

        assert fake_lib.sent["requestUrl"] == f"{URL}?api_key=k"


class TestBody:
    def test_json_is_serialized_and_labelled(self, session, fake_lib):
        session.post(URL, json={"name": "tls", "ids": [1, 2]})

        assert json.loads(fake_lib.sent["requestBody"]) == {"name": "tls", "ids": [1, 2]}
        assert header_values(fake_lib.sent["headers"], "Content-Type") == ["application/json"]

    def test_json_string_is_sent_verbatim(self, session, fake_lib):
        session.post(URL, json='{"already": "encoded"}')

        assert fake_lib.sent["requestBody"] == '{"already": "encoded"}'

    def test_form_data_is_url_encoded_and_labelled(self, session, fake_lib):
        session.post(URL, data={"user": "a b", "role": ["x", "y"]})

        assert fake_lib.sent["requestBody"] == "user=a+b&role=x&role=y"
        assert header_values(fake_lib.sent["headers"], "Content-Type") == ["application/x-www-form-urlencoded"]

    def test_string_data_is_sent_verbatim_without_a_content_type(self, session, fake_lib):
        session.post(URL, data="raw text")

        assert fake_lib.sent["requestBody"] == "raw text"
        assert fake_lib.sent["isByteRequest"] is False
        assert header_values(fake_lib.sent["headers"], "Content-Type") == []

    def test_bytes_are_base64_encoded_and_flagged_for_the_library(self, session, fake_lib):
        body = b"\x00\xffbinary\x10"

        session.post(URL, data=body)

        assert fake_lib.sent["isByteRequest"] is True
        assert base64.b64decode(fake_lib.sent["requestBody"]) == body

    def test_response_body_is_requested_as_bytes(self, session, fake_lib):
        session.get(URL)

        assert fake_lib.sent["isByteResponse"] is True

    def test_data_takes_precedence_over_json(self, session, fake_lib):
        session.post(URL, data={"from": "data"}, json={"from": "json"})

        assert fake_lib.sent["requestBody"] == "from=data"

    def test_content_type_set_on_the_session_is_kept(self, session, fake_lib):
        session.headers["Content-Type"] = "application/vnd.api+json"

        session.post(URL, json={"a": 1})

        assert header_values(fake_lib.sent["headers"], "Content-Type") == ["application/vnd.api+json"]

    def test_content_type_passed_with_the_request_wins(self, session, fake_lib):
        session.post(URL, json={"a": 1}, headers={"content-type": "text/plain"})

        assert header_values(fake_lib.sent["headers"], "Content-Type") == ["text/plain"]

    def test_inferred_content_type_applies_to_one_request_only(self, session, fake_lib):
        session.post(URL, json={"a": 1})
        session.post(URL, data={"a": "1"})
        assert header_values(fake_lib.sent["headers"], "Content-Type") == ["application/x-www-form-urlencoded"]

        session.post(URL, data="raw")
        assert header_values(fake_lib.sent["headers"], "Content-Type") == []
        assert "Content-Type" not in session.headers

    def test_content_type_set_to_none_suppresses_the_inferred_one(self, session, fake_lib):
        session.post(URL, json={"a": 1}, headers={"Content-Type": None})

        assert header_values(fake_lib.sent["headers"], "Content-Type") == []

    @pytest.mark.parametrize("method", ["post", "put", "patch"])
    def test_body_verbs_take_data_as_second_positional_argument(self, session, fake_lib, method):
        getattr(session, method)(URL, {"k": "v"})

        assert fake_lib.sent["requestBody"] == "k=v"


class TestHeaders:
    def test_request_headers_override_session_headers_regardless_of_case(self, session, fake_lib):
        session.get(URL, headers={"user-agent": "custom/1.0"})

        assert header_values(fake_lib.sent["headers"], "User-Agent") == ["custom/1.0"]

    def test_request_headers_are_added_to_session_headers(self, session, fake_lib):
        session.headers["X-Session"] = "s"

        session.get(URL, headers={"X-Request": "r"})

        assert fake_lib.sent["headers"]["X-Session"] == "s"
        assert fake_lib.sent["headers"]["X-Request"] == "r"

    def test_header_set_to_none_is_not_sent(self, session, fake_lib):
        session.get(URL, headers={"accept-encoding": None})

        assert header_values(fake_lib.sent["headers"], "Accept-Encoding") == []

    def test_request_headers_leave_session_headers_untouched(self, session, fake_lib):
        session.get(URL, headers={"X-Once": "1", "Accept": None})

        assert "X-Once" not in session.headers
        assert session.headers["Accept"] == "*/*"

    def test_request_header_order_replaces_the_session_order(self, fake_lib):
        with Session(header_order=["accept", "user-agent"]) as session:
            session.get(URL)
            assert fake_lib.sent["headerOrder"] == ["accept", "user-agent"]

            session.get(URL, header_order=["user-agent", "accept"])
            assert fake_lib.sent["headerOrder"] == ["user-agent", "accept"]


class TestCookies:
    def test_session_and_request_cookies_are_sent_together(self, session, fake_lib):
        session.cookies.set("from_session", "1")

        session.get(URL, cookies={"from_request": "2"})

        assert sent_cookies(fake_lib.sent) == {"from_session": "1", "from_request": "2"}

    def test_request_cookie_replaces_session_cookie_of_the_same_name(self, session, fake_lib):
        session.cookies.set("token", "old")

        session.get(URL, cookies={"token": "new"})

        assert fake_lib.sent["requestCookies"] == [{"domain": "", "name": "token", "path": "/", "value": "new"}]

    def test_double_quotes_are_stripped_from_values(self, session, fake_lib):
        session.get(URL, cookies={"quoted": '"abc"'})

        assert sent_cookies(fake_lib.sent) == {"quoted": "abc"}

    def test_expiry_is_only_sent_for_persistent_cookies(self, session, fake_lib):
        session.cookies.set("session_only", "1")
        session.cookies.set("persistent", "2", domain="example.com", path="/api", expires=4102444800)

        session.get(URL)

        by_name = {cookie["name"]: cookie for cookie in fake_lib.sent["requestCookies"]}
        assert by_name["session_only"] == {"domain": "", "name": "session_only", "path": "/", "value": "1"}
        assert by_name["persistent"] == {
            "domain": "example.com",
            "name": "persistent",
            "path": "/api",
            "value": "2",
            "expires": 4102444800,
        }

    def test_cookies_from_the_response_are_kept_for_the_next_request(self, session, fake_lib):
        fake_lib.reply_with(headers={"Set-Cookie": ["a=1; Path=/", "b=2; Path=/"]})

        response = session.get(URL)
        session.get(URL)

        assert dict(response.cookies) == {"a": "1", "b": "2"}
        assert dict(session.cookies) == {"a": "1", "b": "2"}
        assert sent_cookies(fake_lib.sent) == {"a": "1", "b": "2"}


class TestTransportOptions:
    @pytest.mark.parametrize(
        ("proxies", "expected"),
        [
            ("http://user:pass@proxy:8080", "http://user:pass@proxy:8080"),
            ({"http": "http://proxy:8080", "https": "http://ignored:8080"}, "http://proxy:8080"),
            ({}, ""),
        ],
    )
    def test_session_proxy_is_resolved_to_one_url(self, session, fake_lib, proxies, expected):
        session.proxies = proxies

        session.get(URL)

        assert fake_lib.sent["proxyUrl"] == expected

    def test_request_proxy_wins_over_session_proxy(self, session, fake_lib):
        session.proxies = {"http": "http://session-proxy:8080"}

        session.get(URL, proxy="http://request-proxy:8080")

        assert fake_lib.sent["proxyUrl"] == "http://request-proxy:8080"

    def test_request_timeout_wins_over_session_timeout(self, session, fake_lib):
        session.timeout_seconds = 12

        session.get(URL)
        assert fake_lib.sent["timeoutSeconds"] == 12

        session.get(URL, timeout_seconds=3)
        assert fake_lib.sent["timeoutSeconds"] == 3

    @pytest.mark.parametrize(
        ("session_kwargs", "request_kwargs", "payload_key"),
        [
            ({"force_http1": True}, {}, "forceHttp1"),
            ({"catch_panics": True}, {}, "catchPanics"),
            ({"debug": True}, {}, "withDebug"),
            ({}, {"allow_redirects": True}, "followRedirects"),
            ({}, {"insecure_skip_verify": True}, "insecureSkipVerify"),
        ],
    )
    def test_boolean_option_is_off_by_default_and_forwarded_when_set(
        self, fake_lib, session_kwargs, request_kwargs, payload_key
    ):
        with Session() as default, Session(**session_kwargs) as configured:
            default.get(URL)
            assert fake_lib.sent[payload_key] is False

            configured.get(URL, **request_kwargs)
            assert fake_lib.sent[payload_key] is True

    def test_certificate_pins_are_only_sent_when_configured(self, fake_lib):
        pins = {"example.com": ["NQvy9sFS99nBqk/nZCUF44hFhshrkvxqYtfrZq3i+Ww="]}

        with Session(certificate_pinning=pins) as pinned, Session() as unpinned:
            pinned.get(URL)
            assert fake_lib.sent["certificatePinningHosts"] == pins

            unpinned.get(URL)
            assert "certificatePinningHosts" not in fake_lib.sent


class TestTlsProfile:
    def test_preset_is_sent_by_name(self, fake_lib):
        with Session(client_identifier="firefox_120", random_tls_extension_order=True) as session:
            session.get(URL)

        assert fake_lib.sent["tlsClientIdentifier"] == "firefox_120"
        assert fake_lib.sent["withRandomTLSExtensionOrder"] is True
        assert "customTlsClient" not in fake_lib.sent

    def test_custom_settings_are_sent_under_the_keys_the_library_expects(self, fake_lib):
        ja3 = "771,4865-4866-4867,0-23-65281-10-11-35-16-5-13-18-51-45-43-27,29-23-24,0"
        priority_frames = [{"streamID": 3, "priorityParam": {"weight": 201, "streamDep": 0, "exclusive": False}}]

        with Session(
            client_identifier=None,
            ja3_string=ja3,
            h2_settings={"HEADER_TABLE_SIZE": 65536},
            h2_settings_order=["HEADER_TABLE_SIZE"],
            supported_signature_algorithms=["ECDSAWithP256AndSHA256"],
            supported_delegated_credentials_algorithms=["PSSWithSHA256"],
            supported_versions=["1.3", "1.2"],
            key_share_curves=["X25519"],
            cert_compression_algo="brotli",
            pseudo_header_order=[":method", ":authority", ":scheme", ":path"],
            connection_flow=15663105,
            priority_frames=priority_frames,
            header_priority={"streamDep": 1, "exclusive": True, "weight": 1},
            alpn_protocols=["http/1.1"],
            alps_protocols=["h2"],
        ) as session:
            session.get(URL)

        assert "tlsClientIdentifier" not in fake_lib.sent
        assert fake_lib.sent["customTlsClient"] == {
            "ja3String": ja3,
            "h2Settings": {"HEADER_TABLE_SIZE": 65536},
            "h2SettingsOrder": ["HEADER_TABLE_SIZE"],
            "pseudoHeaderOrder": [":method", ":authority", ":scheme", ":path"],
            "connectionFlow": 15663105,
            "priorityFrames": priority_frames,
            "headerPriority": {"streamDep": 1, "exclusive": True, "weight": 1},
            "certCompressionAlgos": ["brotli"],
            "supportedVersions": ["1.3", "1.2"],
            "supportedSignatureAlgorithms": ["ECDSAWithP256AndSHA256"],
            "supportedDelegatedCredentialsAlgorithms": ["PSSWithSHA256"],
            "keyShareCurves": ["X25519"],
            "alpnProtocols": ["http/1.1"],
            "alpsProtocols": ["h2"],
        }

    def test_custom_settings_offer_h2_and_http1_over_alpn_by_default(self, fake_lib):
        # The JA3 extension 16 is sent with whatever is here, and servers reject it empty.
        with Session(client_identifier=None, ja3_string="771,4865,0-16,29,0") as session:
            session.get(URL)

        assert fake_lib.sent["customTlsClient"]["alpnProtocols"] == ["h2", "http/1.1"]
        assert fake_lib.sent["customTlsClient"]["alpsProtocols"] is None


class TestLifecycle:
    @pytest.mark.parametrize("method", ["GET", "OPTIONS", "HEAD", "POST", "PUT", "PATCH", "DELETE"])
    def test_verb_helper_sends_its_method(self, session, fake_lib, method):
        getattr(session, method.lower())(URL)

        assert fake_lib.sent["requestMethod"] == method

    def test_requests_share_the_session_id_of_their_session_only(self, fake_lib):
        with Session() as first, Session() as second:
            first.get(URL)
            first.get(URL)
            second.get(URL)

        ids = [payload["sessionId"] for payload in fake_lib.payloads]
        assert ids[0] == ids[1]
        assert ids[1] != ids[2]

    def test_library_error_is_raised_as_tls_client_exception(self, session, fake_lib):
        fake_lib.reply_with(status=0, body="failed to do request: dial tcp: connection refused")

        with pytest.raises(TLSClientException, match="connection refused"):
            session.get(URL)

    def test_reply_memory_is_freed_after_success_and_after_error(self, session, fake_lib):
        fake_lib.reply_with(status=200)
        fake_lib.reply_with(status=0, body="boom")

        session.get(URL)
        with pytest.raises(TLSClientException):
            session.get(URL)

        assert fake_lib.freed_ids == ["response-1", "response-2"]

    def test_close_destroys_the_native_session_and_frees_the_reply(self, fake_lib):
        session = Session()
        session.get(URL)

        session.close()

        session_id = fake_lib.sent["sessionId"]
        assert fake_lib.destroyed_session_ids == [session_id]
        assert fake_lib.freed_ids[-1] == f"destroy-{session_id}"

    def test_leaving_the_with_block_closes_the_session_even_on_error(self, fake_lib):
        with pytest.raises(RuntimeError), Session() as session:
            session.get(URL)
            raise RuntimeError

        assert fake_lib.destroyed_session_ids == [fake_lib.sent["sessionId"]]
