import asyncio
import base64
import socket
from collections.abc import Iterator

import pytest
from httpbin.core import resource as httpbin_resource

from tls_client import AsyncSession, Session
from tls_client.exceptions import TLSClientException, TooManyRedirects

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
        # write_bytes, so Windows doesn't turn the newline into \r\n
        path.write_bytes("café\n".encode())

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

    @pytest.mark.parametrize("path", ["/redirect/3", "/relative-redirect/3", "/absolute-redirect/3"])
    def test_followed_when_allowed(self, httpbin, session, path):
        response = session.get(f"{httpbin.url}{path}", allow_redirects=True)

        assert response.status_code == 200
        assert response.url == f"{httpbin.url}/get"
        assert [r.status_code for r in response.history] == [302, 302, 302]
        assert response.history[0].url == f"{httpbin.url}{path}"

    def test_redirect_to_a_relative_url(self, httpbin, session):
        response = session.get(f"{httpbin.url}/redirect-to", params={"url": "/get?a=1"}, allow_redirects=True)

        assert response.url == f"{httpbin.url}/get?a=1"
        assert response.json()["args"] == {"a": "1"}

    @pytest.mark.parametrize(
        ("status", "method"), [(301, "GET"), (302, "GET"), (303, "GET"), (307, "POST"), (308, "POST")]
    )
    def test_post_is_resent_as_the_status_requires(self, httpbin, session, status, method):
        response = session.post(
            f"{httpbin.url}/redirect-to",
            params={"url": "/anything", "status_code": status},
            data={"a": "1"},
            allow_redirects=True,
        )

        echoed = response.json()
        assert echoed["method"] == method
        if method == "POST":
            assert echoed["form"] == {"a": "1"}
            assert echoed["headers"]["Content-Type"] == "application/x-www-form-urlencoded"
        else:
            assert echoed["form"] == {}
            assert "Content-Type" not in echoed["headers"]

    def test_too_many_redirects_raise(self, httpbin, session):
        with pytest.raises(TooManyRedirects):
            session.get(f"{httpbin.url}/redirect/31", allow_redirects=True)

    def test_credentials_and_cookies_stay_with_their_host(self, httpbin, session):
        session.get(f"{httpbin.url}/cookies/set", params={"flavor": "oat"})
        other_host = httpbin.url.replace("127.0.0.1", "localhost")

        response = session.get(
            f"{httpbin.url}/redirect-to",
            params={"url": f"{other_host}/headers"},
            headers={"Authorization": "Bearer secret", "X-Custom": "1"},
            allow_redirects=True,
        )

        received = response.json()["headers"]
        assert received["Host"] == other_host.removeprefix("http://")
        assert received["X-Custom"] == "1"
        assert "Authorization" not in received
        assert "Cookie" not in received


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

    def test_cookie_set_by_a_redirect_is_stored_and_sent_to_its_target(self, httpbin, session):
        # /cookies/set answers with the cookie and a redirect to /cookies, which echoes the cookies it receives.
        response = session.get(f"{httpbin.url}/cookies/set", params={"flavor": "oat"}, allow_redirects=True)

        assert response.history[0].status_code == 302
        assert response.json() == {"cookies": {"flavor": "oat"}}
        assert response.cookies["flavor"] == "oat"
        assert session.cookies["flavor"] == "oat"

    def test_cookie_set_by_a_redirect_reaches_the_async_session_jar(self, httpbin):
        async def main():
            async with AsyncSession() as session:
                await session.get(f"{httpbin.url}/cookies/set", params={"flavor": "oat"}, allow_redirects=True)
                return session.cookies.get_dict()

        assert asyncio.run(main()) == {"flavor": "oat"}

    def test_cleared_cookies_are_no_longer_sent(self, httpbin, session):
        session.get(f"{httpbin.url}/cookies/set", params={"flavor": "oat"})
        assert session.get(f"{httpbin.url}/cookies").json() == {"cookies": {"flavor": "oat"}}

        session.cookies.clear()

        assert session.get(f"{httpbin.url}/cookies").json() == {"cookies": {}}

    def test_removed_cookie_is_no_longer_sent(self, httpbin, session):
        session.get(f"{httpbin.url}/cookies/set", params={"flavor": "oat", "size": "big"})

        del session.cookies["flavor"]

        assert session.get(f"{httpbin.url}/cookies").json() == {"cookies": {"size": "big"}}

    def test_cookie_deleted_by_the_server_is_no_longer_sent(self, httpbin, session):
        session.get(f"{httpbin.url}/cookies/set", params={"flavor": "oat", "size": "big"})

        session.get(f"{httpbin.url}/cookies/delete", params={"flavor": ""})

        assert "flavor" not in session.cookies
        assert session.get(f"{httpbin.url}/cookies").json() == {"cookies": {"size": "big"}}


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
