import json
from collections import deque
from collections.abc import Iterator
from typing import Any

import pytest

import tls_client.sessions


class FakeLibrary:
    """Stands in for the Go shared library: records every call and answers with canned JSON."""

    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []
        self.freed_ids: list[str] = []
        self.destroyed_session_ids: list[str] = []
        self._replies: deque[dict[str, Any]] = deque()

    @property
    def sent(self) -> dict[str, Any]:
        """Payload of the most recent request."""
        return self.payloads[-1]

    def reply_with(self, **fields: Any) -> None:
        """Queue fields for the next reply; anything left out gets the default of a 200 with an empty body."""
        self._replies.append(fields)

    def request(self, payload: bytes) -> bytes:
        sent = json.loads(payload)
        self.payloads.append(sent)
        reply = {
            "id": f"response-{len(self.payloads)}",
            "sessionId": sent["sessionId"],
            "status": 200,
            "target": sent["requestUrl"],
            "body": "",
            "headers": {},
            "cookies": {},
            "usedProtocol": "HTTP/2.0",
        }
        if self._replies:
            reply.update(self._replies.popleft())
        return json.dumps(reply).encode()

    def free_memory(self, response_id: bytes) -> None:
        self.freed_ids.append(response_id.decode())

    def destroy_session(self, payload: bytes) -> bytes:
        session_id = json.loads(payload)["sessionId"]
        self.destroyed_session_ids.append(session_id)
        return json.dumps({"id": f"destroy-{session_id}", "success": True}).encode()


@pytest.fixture
def fake_lib(monkeypatch: pytest.MonkeyPatch) -> FakeLibrary:
    lib = FakeLibrary()
    monkeypatch.setattr(tls_client.sessions, "request", lib.request)
    monkeypatch.setattr(tls_client.sessions, "freeMemory", lib.free_memory)
    monkeypatch.setattr(tls_client.sessions, "destroySession", lib.destroy_session)
    return lib


@pytest.fixture
def session(fake_lib: FakeLibrary) -> Iterator[tls_client.Session]:
    with tls_client.Session() as s:
        yield s
