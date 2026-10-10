import inspect
import queue
import socket
import struct
import threading
from collections.abc import Callable, Iterable, Iterator
from typing import Any

import pytest

from tls_client import Session
from tls_client.exceptions import TLSClientException
from tls_client.settings import CLIENT_IDENTIFIERS

# Upstream's own default (profiles.DefaultClientProfile in tls-client v1.16.0), which it uses for unknown names.
# These identifiers send the same ClientHello as the fallback, so the wire can't tell them apart from a typo.
UPSTREAM_DEFAULT_PROFILES = {"chrome_150", "chrome_150_PSK"}

# Extensions whose content changes on every connection; only their presence is compared.
# SNI, padding, pre_shared_key and the GREASE encrypted_client_hello.
VOLATILE_EXTENSIONS = {0, 21, 41, 65037}


class TestValidation:
    @pytest.mark.parametrize("identifier", CLIENT_IDENTIFIERS)
    def test_every_listed_identifier_is_accepted(self, identifier):
        assert Session(client_identifier=identifier).client_identifier == identifier

    def test_default_identifier_is_listed(self):
        default = inspect.signature(Session).parameters["client_identifier"].default

        assert default in CLIENT_IDENTIFIERS

    def test_none_selects_a_custom_tls_configuration(self):
        assert Session(client_identifier=None, ja3_string="771,4865,0,29,0").client_identifier is None

    @pytest.mark.parametrize(
        ("identifier", "suggestion"),
        [
            # The typos that used to be in the README.
            ("chrome109", "chrome_109"),
            ("Chrome110", "chrome_110"),
            ("firefox108", "firefox_108"),
            ("Firefox110", "firefox_110"),
            ("CHROME_120", "chrome_120"),
            ("chrome_116_psk", "chrome_116_PSK"),
        ],
    )
    def test_unknown_identifier_is_rejected_with_close_matches(self, identifier, suggestion):
        with pytest.raises(ValueError, match=f"Unknown client_identifier '{identifier}'") as rejected:
            Session(client_identifier=identifier)

        assert f"'{suggestion}'" in str(rejected.value)

    def test_unknown_identifier_without_close_matches_points_to_the_full_list(self):
        with pytest.raises(ValueError, match="Unknown client_identifier 'edge_120'") as rejected:
            Session(client_identifier="edge_120")

        assert "Did you mean" not in str(rejected.value)
        assert "tls_client/settings.py" in str(rejected.value)


def is_grease(value: int) -> bool:
    return value & 0x0F0F == 0x0A0A and value >> 8 == value & 0xFF


def u16s(data: bytes) -> tuple[int, ...]:
    return without_grease(struct.unpack(f"!{len(data) // 2}H", data))


def without_grease(values: Iterable[int]) -> tuple[int, ...]:
    # GREASE values are random per connection, so they all compare as one placeholder.
    return tuple(0x0A0A if is_grease(v) else v for v in values)


def fingerprint(record: bytes) -> tuple[Any, ...]:
    """The parts of a ClientHello record that identify the profile, with per-connection randomness stripped out."""
    hello = record[5 + 4 :]  # record header, handshake header
    pos = 2 + 32  # legacy_version, random
    pos += 1 + hello[pos]  # session id
    (length,) = struct.unpack_from("!H", hello, pos)
    ciphers = u16s(hello[pos + 2 : pos + 2 + length])
    pos += 2 + length
    pos += 1 + hello[pos]  # compression methods
    (length,) = struct.unpack_from("!H", hello, pos)
    pos, end = pos + 2, pos + 2 + length

    extensions: dict[int, Any] = {}
    while pos < end:
        kind, length = struct.unpack_from("!HH", hello, pos)
        data = hello[pos + 4 : pos + 4 + length]
        pos += 4 + length
        if is_grease(kind):
            continue
        if kind in VOLATILE_EXTENSIONS:
            extensions[kind] = None
        elif kind == 10:  # supported_groups
            extensions[kind] = u16s(data[2:])
        elif kind == 43:  # supported_versions
            extensions[kind] = u16s(data[1:])
        elif kind == 51:  # key_share: the groups, not the random keys
            groups: list[int] = []
            offset = 2
            while offset < len(data):
                group, key_length = struct.unpack_from("!HH", data, offset)
                groups.append(group)
                offset += 4 + key_length
            extensions[kind] = without_grease(groups)
        else:
            extensions[kind] = data
    # Sorted, because several profiles shuffle their extension order on every connection.
    return ciphers, tuple(sorted(extensions.items()))


def recv_exactly(conn: socket.socket, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = conn.recv(size - len(data))
        if not chunk:
            raise ConnectionError("client closed the connection mid-record")
        data += chunk
    return data


@pytest.fixture(scope="module")
def client_hello() -> Iterator[Callable[[str], tuple[Any, ...]]]:
    """Returns a function that sends one request with a profile and gives back the fingerprint of its ClientHello.

    A local TCP server reads the first TLS record and hangs up, so no certificate or external network is needed.
    """
    server = socket.create_server(("127.0.0.1", 0))
    url = f"https://127.0.0.1:{server.getsockname()[1]}/"
    records: queue.Queue[bytes] = queue.Queue()

    def serve() -> None:
        while True:
            try:
                conn, _ = server.accept()
            except OSError:  # server closed during teardown
                return
            with conn:
                try:
                    header = recv_exactly(conn, 5)
                    (length,) = struct.unpack("!H", header[3:])
                    records.put(header + recv_exactly(conn, length))
                except ConnectionError:
                    continue  # the test waiting for this record times out and fails

    threading.Thread(target=serve, daemon=True).start()

    def send(identifier: str) -> tuple[Any, ...]:
        with Session() as session:
            # Assigned after __init__ so unknown names reach the library unvalidated.
            session.client_identifier = identifier
            with pytest.raises(TLSClientException):
                session.get(url)
        return fingerprint(records.get(timeout=10))

    yield send
    server.close()


@pytest.fixture(scope="module")
def fallback_hello(client_hello: Callable[[str], tuple[Any, ...]]) -> tuple[Any, ...]:
    """What the library sends for a name it doesn't know."""
    return client_hello("not_a_real_profile")


@pytest.mark.integration
@pytest.mark.parametrize("identifier", sorted(UPSTREAM_DEFAULT_PROFILES))
def test_unknown_names_fall_back_to_the_upstream_default(client_hello, fallback_hello, identifier):
    # The library never reports an unknown name, it swaps in its default profile. Detecting that swap is what makes
    # the next test meaningful.
    assert client_hello(identifier) == fallback_hello


@pytest.mark.integration
@pytest.mark.parametrize("identifier", sorted(set(CLIENT_IDENTIFIERS) - UPSTREAM_DEFAULT_PROFILES))
def test_the_library_knows_every_listed_identifier(client_hello, fallback_hello, identifier):
    assert client_hello(identifier) != fallback_hello, (
        f"{identifier} sends the fallback ClientHello, so the native library doesn't have this profile"
    )
