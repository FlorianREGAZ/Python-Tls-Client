"""Real requests through the native library against a stdlib HTTP server, for bodies and headers httpbin can't
produce byte for byte."""

import base64
import json
import os
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from tls_client import Session
from tls_client.exceptions import TLSClientException

pytestmark = pytest.mark.integration

# A 1x1 PNG, the kind of download that used to arrive mangled.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
LARGE = os.urandom(8 * 1024 * 1024)
# How long /slow takes to answer.
SLOW_SECONDS = 0.6

# Path -> (Content-Type, body)
BODIES = {
    "/bytes": ("application/octet-stream", bytes(range(256))),
    "/png": ("image/png", PNG),
    "/large": ("application/octet-stream", LARGE),
    "/empty": ("text/plain", b""),
    "/json": ("application/json", json.dumps({"name": "tls", "ids": [1, 2]}).encode()),
    "/utf8": ("text/plain", "∮ E⋅da = Q".encode()),
    "/latin-1": ("text/plain; charset=iso-8859-1", "café".encode("latin-1")),
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        if self.path == "/headers":
            self.echo_headers()
        elif self.path == "/slow":
            time.sleep(SLOW_SECONDS)
            self.reply("text/plain", b"done")
        else:
            content_type, body = BODIES[self.path]
            self.reply(content_type, body, {"x-MiXeD-case": "yes"})

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.echo_headers()

    def echo_headers(self) -> None:
        received = {name.lower(): value for name, value in self.headers.items()}
        self.reply("application/json", json.dumps(received).encode())

    def reply(self, content_type: str, body: bytes, extra_headers: dict[str, str] | None = None) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        try:
            self.end_headers()
            self.wfile.write(body)
        except ConnectionError:
            # The client gave up waiting, as the timeout tests make it do.
            pass

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture(scope="module")
def server_url() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


@pytest.fixture
def session() -> Iterator[Session]:
    with Session() as s:
        yield s


class TestBody:
    @pytest.mark.parametrize("path", ["/bytes", "/png", "/large"])
    def test_binary_body_arrives_byte_for_byte(self, server_url, session, path):
        response = session.get(f"{server_url}{path}")

        assert response.status_code == 200
        assert response.content == BODIES[path][1]

    def test_empty_body(self, server_url, session):
        response = session.get(f"{server_url}/empty")

        assert response.content == b""
        assert response.text == ""

    def test_json_body(self, server_url, session):
        assert session.get(f"{server_url}/json").json() == {"name": "tls", "ids": [1, 2]}

    def test_text_defaults_to_utf8(self, server_url, session):
        assert session.get(f"{server_url}/utf8").text == "∮ E⋅da = Q"

    def test_text_uses_the_charset_from_the_content_type_header(self, server_url, session):
        response = session.get(f"{server_url}/latin-1")

        assert response.content == "café".encode("latin-1")
        assert response.encoding == "iso-8859-1"
        assert response.text == "café"


class TestHeaders:
    @pytest.mark.parametrize("name", ["X-Mixed-Case", "x-mixed-case", "X-MIXED-CASE"])
    def test_response_header_lookup_ignores_case(self, server_url, session, name):
        response = session.get(f"{server_url}/bytes")

        assert response.headers[name] == "yes"
        assert response.headers["content-type"] == "application/octet-stream"

    def test_inferred_content_type_does_not_leak_into_later_requests(self, server_url, session):
        json_post = session.post(f"{server_url}/headers", json={"a": 1}).json()
        form_post = session.post(f"{server_url}/headers", data={"a": "1"}).json()
        get = session.get(f"{server_url}/headers").json()

        assert json_post["content-type"] == "application/json"
        assert form_post["content-type"] == "application/x-www-form-urlencoded"
        assert "content-type" not in get
        assert "Content-Type" not in session.headers

    def test_content_type_from_the_session_or_the_request_is_kept(self, server_url, session):
        session.headers["content-type"] = "application/vnd.api+json"

        from_session = session.post(f"{server_url}/headers", json={"a": 1}).json()
        from_request = session.post(
            f"{server_url}/headers", json={"a": 1}, headers={"CONTENT-TYPE": "text/plain"}
        ).json()

        assert from_session["content-type"] == "application/vnd.api+json"
        assert from_request["content-type"] == "text/plain"


class TestTimeout:
    @pytest.mark.parametrize("kwarg", ["timeout", "timeout_seconds"])
    def test_fractional_timeout_is_applied(self, server_url, session, kwarg):
        with pytest.raises(TLSClientException, match="Timeout exceeded"):
            session.get(f"{server_url}/slow", **{kwarg: SLOW_SECONDS / 3})

    def test_response_within_the_timeout_arrives(self, server_url, session):
        assert session.get(f"{server_url}/slow", timeout=SLOW_SECONDS * 4).text == "done"

    def test_fractional_session_timeout_is_applied(self, server_url, session):
        session.timeout_seconds = SLOW_SECONDS / 3

        with pytest.raises(TLSClientException, match="Timeout exceeded"):
            session.get(f"{server_url}/slow")
