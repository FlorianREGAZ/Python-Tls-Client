import asyncio
import json
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from tls_client import AsyncSession

pytestmark = pytest.mark.integration

SLOW_SECONDS = 0.3


class Server(ThreadingHTTPServer):
    # The default backlog of 5 makes the OS drop connections when 20 requests arrive at once.
    request_queue_size = 64

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), Handler)
        self.lock = threading.Lock()
        self.in_flight = 0
        self.peak_in_flight = 0

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}"


class Handler(BaseHTTPRequestHandler):
    """/echo returns the request as JSON, /slow answers after SLOW_SECONDS, /cookie/<name> sets that cookie."""

    server: Server

    def do_GET(self) -> None:
        self.respond()

    def do_POST(self) -> None:
        self.respond()

    def respond(self) -> None:
        with self.server.lock:
            self.server.in_flight += 1
            self.server.peak_in_flight = max(self.server.peak_in_flight, self.server.in_flight)
        try:
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode()
            self.send_response(200)
            if self.path == "/slow":
                time.sleep(SLOW_SECONDS)
            elif self.path.startswith("/cookie/"):
                name = self.path.removeprefix("/cookie/")
                self.send_header("Set-Cookie", f"{name}={name}-value; Path=/")
            payload = json.dumps(
                {"method": self.command, "path": self.path, "headers": dict(self.headers), "body": body}
            ).encode()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        finally:
            with self.server.lock:
                self.server.in_flight -= 1

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def server() -> Iterator[Server]:
    srv = Server()
    thread = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    yield srv
    srv.shutdown()
    srv.server_close()
    thread.join()


def test_get_and_post_reach_the_server(server):
    async def main():
        async with AsyncSession() as session:
            got = await session.get(f"{server.url}/echo", params={"q": "1"})
            posted = await session.post(f"{server.url}/echo", json={"name": "tls"})
            return got, posted

    got, posted = asyncio.run(main())

    assert got.status_code == 200
    assert got.json()["method"] == "GET"
    assert got.json()["path"] == "/echo?q=1"
    assert posted.json()["method"] == "POST"
    assert json.loads(posted.json()["body"]) == {"name": "tls"}
    assert posted.json()["headers"]["Content-Type"] == "application/json"


def test_constructor_arguments_reach_the_session(server):
    async def main():
        async with AsyncSession(client_identifier="firefox_120", force_http1=True) as session:
            return session, await session.get(f"{server.url}/echo")

    session, response = asyncio.run(main())

    assert session.session.client_identifier == "firefox_120"
    assert session.session.force_http1 is True
    assert response.status_code == 200


def test_session_headers_are_sent(server):
    async def main():
        async with AsyncSession() as session:
            session.headers["X-Session"] = "1"
            return await session.get(f"{server.url}/echo", headers={"X-Request": "2"})

    received = asyncio.run(main()).json()["headers"]

    assert received["X-Session"] == "1"
    assert received["X-Request"] == "2"


def test_concurrent_requests_overlap(server):
    count = 20

    async def main():
        with ThreadPoolExecutor(max_workers=count) as executor:
            async with AsyncSession(executor=executor) as session:
                start = time.perf_counter()
                responses = await asyncio.gather(*(session.get(f"{server.url}/slow") for _ in range(count)))
                return responses, time.perf_counter() - start

    responses, elapsed = asyncio.run(main())

    assert [r.status_code for r in responses] == [200] * count
    # Serially this takes count * SLOW_SECONDS = 6s.
    assert elapsed < count * SLOW_SECONDS / 3
    assert server.peak_in_flight > count / 2


def test_cookies_from_concurrent_responses_all_end_up_in_the_jar(server):
    names = [f"c{i}" for i in range(20)]

    async def main():
        with ThreadPoolExecutor(max_workers=len(names)) as executor:
            async with AsyncSession(executor=executor) as session:
                await asyncio.gather(*(session.get(f"{server.url}/cookie/{name}") for name in names))
                sent_back = await session.get(f"{server.url}/echo")
                return session.cookies.get_dict(), sent_back

    jar, sent_back = asyncio.run(main())

    assert jar == {name: f"{name}-value" for name in names}
    sent_cookies = dict(pair.split("=") for pair in sent_back.json()["headers"]["Cookie"].split("; "))
    assert sent_cookies == jar


def test_concurrent_bodies_keep_their_own_content_type(server):
    async def main():
        async with AsyncSession() as session:
            responses = await asyncio.gather(
                *(session.post(f"{server.url}/echo", json={"i": i}) for i in range(5)),
                *(session.post(f"{server.url}/echo", data={"i": i}) for i in range(5)),
            )
            return session, responses

    session, responses = asyncio.run(main())

    content_types = [r.json()["headers"]["Content-Type"] for r in responses]
    assert content_types == ["application/json"] * 5 + ["application/x-www-form-urlencoded"] * 5
    assert "Content-Type" not in session.headers
