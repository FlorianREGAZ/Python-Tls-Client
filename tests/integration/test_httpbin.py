import base64
import socket
from collections.abc import Iterator

import pytest
from httpbin.core import resource as httpbin_resource

from tls_client import Session
from tls_client.exceptions import TLSClientException

pytestmark = pytest.mark.integration


@pytest.fixture
def session() -> Iterator[Session]:
    with Session() as s:
        yield s


def unused_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port


class TestRequestBody:
    def test_query_params_reach_the_server(self, httpbin, session):
        response = session.get(f"{httpbin.url}/get", params={"q": "a b", "tag": ["x", "y"]})

        assert response.status_code == 200
        assert response.json()["args"] == {"q": "a b", "tag": ["x", "y"]}

    def test_json_body_reaches_the_server(self, httpbin, session):
        response = session.post(f"{httpbin.url}/post", json={"name": "tls", "ids": [1, 2]})

        echoed = response.json()
        assert echoed["json"] == {"name": "tls", "ids": [1, 2]}
        assert echoed["headers"]["Content-Type"] == "application/json"

    def test_form_body_reaches_the_server(self, httpbin, session):
        response = session.post(f"{httpbin.url}/post", data={"user": "a b", "role": ["x", "y"]})

        assert response.json()["form"] == {"user": "a b", "role": ["x", "y"]}

    def test_binary_body_reaches_the_server_unchanged(self, httpbin, session):
        payload = b"\x00\xff\x10binary"

        response = session.post(f"{httpbin.url}/post", data=payload)

        # httpbin reports bodies that are not valid UTF-8 as a base64 data URL.
        assert response.json()["data"] == "data:application/octet-stream;base64," + base64.b64encode(payload).decode()

    def test_files_and_form_fields_reach_the_server_as_multipart(self, httpbin, session, tmp_path):
        path = tmp_path / "notes.txt"
        path.write_text("café\n", encoding="utf-8")

        with path.open("rb") as f:
            response = session.post(
                f"{httpbin.url}/post",
                data={"user": "a b", "role": ["x", "y"]},
                files={"notes": f, "text": ("hello.txt", "∮ E⋅da = Q"), "plain": (None, "field")},
            )

        echoed = response.json()
        assert echoed["headers"]["Content-Type"].startswith("multipart/form-data; boundary=")
        assert echoed["form"] == {"user": "a b", "role": ["x", "y"], "plain": "field"}
        assert echoed["files"] == {"notes": "café\n", "text": "∮ E⋅da = Q"}

    def test_binary_file_reaches_the_server_unchanged(self, httpbin, session):
        payload = bytes(range(256))

        response = session.post(f"{httpbin.url}/post", files={"image": ("pixel.png", payload)})

        # httpbin reports file content that is not valid UTF-8 as a base64 data URL with the part's Content-Type.
        assert response.json()["files"] == {"image": "data:image/png;base64," + base64.b64encode(payload).decode()}

    def test_headers_reach_the_server_and_none_removes_one(self, httpbin, session):
        response = session.get(f"{httpbin.url}/headers", headers={"X-Custom": "1", "Accept": None})

        received = response.json()["headers"]
        assert received["X-Custom"] == "1"
        assert "Accept" not in received


class TestResponse:
    def test_error_status_is_returned_not_raised(self, httpbin, session):
        assert session.get(f"{httpbin.url}/status/418").status_code == 418

    def test_repeated_response_header_arrives_as_a_list(self, httpbin, session):
        response = session.get(f"{httpbin.url}/response-headers", params={"X-Multi": ["a", "b"]})

        assert response.headers["X-Multi"] == ["a", "b"]

    @pytest.mark.parametrize(("path", "flag"), [("gzip", "gzipped"), ("brotli", "brotli")])
    def test_compressed_body_is_decoded(self, httpbin, session, path, flag):
        response = session.get(f"{httpbin.url}/{path}")

        assert response.json()[flag] is True

    def test_utf8_body_is_decoded(self, httpbin, session):
        response = session.get(f"{httpbin.url}/encoding/utf8")

        assert "∮ E⋅da = Q" in response.text

    def test_binary_body_arrives_unchanged(self, httpbin, session):
        response = session.get(f"{httpbin.url}/image/png")

        # httpbin serves this file from its package data.
        assert response.content == httpbin_resource("images/pig_icon.png")


class TestRedirects:
    def test_not_followed_by_default(self, httpbin, session):
        response = session.get(f"{httpbin.url}/redirect-to", params={"url": "/get"})

        assert response.status_code == 302
        assert response.headers["Location"] == "/get"

    def test_followed_when_allowed(self, httpbin, session):
        response = session.get(f"{httpbin.url}/redirect/2", allow_redirects=True)

        assert response.status_code == 200
        assert response.url == f"{httpbin.url}/get"


class TestCookies:
    def test_cookie_set_by_the_server_is_stored_and_sent_back(self, httpbin, session):
        response = session.get(f"{httpbin.url}/cookies/set", params={"flavor": "oat"})

        assert response.cookies["flavor"] == "oat"
        assert session.cookies["flavor"] == "oat"
        assert session.get(f"{httpbin.url}/cookies").json() == {"cookies": {"flavor": "oat"}}

    def test_only_cookies_matching_the_host_are_sent(self, httpbin, session):
        session.cookies.set("host_only", "1")
        session.cookies.set("other_site", "2", domain="example.com")

        response = session.get(f"{httpbin.url}/cookies", cookies={"per_request": "3"})

        assert response.json() == {"cookies": {"host_only": "1", "per_request": "3"}}


class TestFailures:
    def test_refused_connection_raises(self, session):
        with pytest.raises(TLSClientException, match="refused"):
            session.get(f"http://127.0.0.1:{unused_port()}/")

    def test_session_timeout_raises(self, httpbin, session):
        session.timeout_seconds = 1

        with pytest.raises(TLSClientException, match="Timeout exceeded"):
            session.get(f"{httpbin.url}/delay/2")

    @pytest.mark.xfail(reason="the native session keeps the timeout of its first request")
    @pytest.mark.parametrize("kwarg", ["timeout", "timeout_seconds"])
    def test_request_timeout_applies_after_the_first_request(self, httpbin, session, kwarg):
        session.get(f"{httpbin.url}/get")

        with pytest.raises(TLSClientException, match="Timeout exceeded"):
            session.get(f"{httpbin.url}/delay/2", **{kwarg: 1})


class TestCertificateVerification:
    def test_self_signed_certificate_is_rejected(self, httpbin_secure, session):
        with pytest.raises(TLSClientException, match="certificate"):
            session.get(f"{httpbin_secure.url}/get")

    def test_insecure_skip_verify_accepts_self_signed_certificate(self, httpbin_secure, session):
        response = session.get(f"{httpbin_secure.url}/get", insecure_skip_verify=True)

        assert response.status_code == 200
