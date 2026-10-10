import re
from typing import Any

import pytest

from tls_client import Session
from tls_client.exceptions import TLSClientException

pytestmark = pytest.mark.network

# Echoes the TLS ClientHello and HTTP/2 frames it received.
PEET_API = "https://tls.peet.ws/api/all"


def fingerprint(session: Session, **kwargs: Any) -> dict[str, Any]:
    response = session.get(PEET_API, **kwargs)
    assert response.status_code == 200
    result: dict[str, Any] = response.json()
    return result


def extension_order(fp: dict[str, Any]) -> list[str]:
    return fp["tls"]["ja3"].split(",")[2].split("-")


def sent_header_names(fp: dict[str, Any]) -> list[str]:
    if fp["http_version"] == "h2":
        frame = next(f for f in fp["http2"]["sent_frames"] if f["frame_type"] == "HEADERS")
        lines = [line for line in frame["headers"] if not line.startswith(":")]
    else:
        lines = fp["http1"]["headers"]
    return [line.split(":")[0].lower() for line in lines]


# JA4 sorts extensions, so it stays stable for profiles that shuffle them; the Akamai string covers HTTP/2.
@pytest.mark.parametrize(
    ("identifier", "ja4", "akamai"),
    [
        (
            "chrome_120",
            "t13d1516h2_8daaf6152771_02713d6af862",
            "1:65536;2:0;4:6291456;6:262144|15663105|0|m,a,s,p",
        ),
        (
            "firefox_120",
            "t13d1713h2_5b57614c22b0_748f4c70de1c",
            "1:65536;4:131072;5:16384|12517377|3:0:0:201,5:0:0:101,7:0:0:1,9:0:7:1,11:0:3:1,13:0:0:241|m,p,a,s",
        ),
        (
            "safari_ios_17_0",
            "t13d2014h2_a09f3c656075_14788d8d241b",
            "2:0;4:2097152;3:100|10485760|0|m,s,p,a",
        ),
    ],
)
def test_preset_presents_the_browser_fingerprint(identifier, ja4, akamai):
    with Session(client_identifier=identifier) as session:
        fp = fingerprint(session)

    assert fp["tls"]["ja4"] == ja4
    assert fp["http2"]["akamai_fingerprint"] == akamai


def test_custom_tls_configuration_is_what_the_server_sees():
    ja3 = "771,4865-4866-4867-49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53,0-23-65281-10-11-35-16-5-13-18-51-45-43-27,29-23-24,0"

    with Session(
        client_identifier=None,
        ja3_string=ja3,
        h2_settings={
            "HEADER_TABLE_SIZE": 65536,
            "MAX_CONCURRENT_STREAMS": 1000,
            "INITIAL_WINDOW_SIZE": 6291456,
            "MAX_HEADER_LIST_SIZE": 262144,
        },
        h2_settings_order=[
            "HEADER_TABLE_SIZE",
            "MAX_CONCURRENT_STREAMS",
            "INITIAL_WINDOW_SIZE",
            "MAX_HEADER_LIST_SIZE",
        ],
        supported_signature_algorithms=["ECDSAWithP256AndSHA256", "PSSWithSHA256", "PKCS1WithSHA256"],
        supported_versions=["1.3", "1.2"],
        key_share_curves=["X25519"],
        cert_compression_algo="brotli",
        pseudo_header_order=[":method", ":authority", ":scheme", ":path"],
        connection_flow=15663105,
    ) as session:
        fp = fingerprint(session)

    assert fp["tls"]["ja3"] == ja3
    assert fp["http2"]["akamai_fingerprint"] == "1:65536;3:1000;4:6291456;6:262144|15663105|0|m,a,s,p"


def test_extension_order_is_shuffled_only_when_asked():
    def order(**kwargs: Any) -> list[str]:
        with Session(client_identifier="firefox_120", **kwargs) as session:
            return extension_order(fingerprint(session))

    assert order() == order()

    shuffled_first, shuffled_second = order(random_tls_extension_order=True), order(random_tls_extension_order=True)
    assert shuffled_first != shuffled_second
    assert sorted(shuffled_first) == sorted(shuffled_second) == sorted(order())


@pytest.mark.parametrize(("force_http1", "expected"), [(False, "h2"), (True, "HTTP/1.1")])
def test_force_http1_selects_the_protocol(force_http1, expected):
    with Session(force_http1=force_http1) as session:
        assert fingerprint(session)["http_version"] == expected


@pytest.mark.parametrize("force_http1", [False, True])
def test_header_order_is_kept_on_the_wire(force_http1):
    with Session(force_http1=force_http1) as session:
        fp = fingerprint(session, headers={"X-B": "2", "X-A": "1"}, header_order=["x-a", "accept", "x-b"])

    assert sent_header_names(fp)[:3] == ["x-a", "accept", "x-b"]


def test_certificate_pinning_accepts_a_matching_pin_and_rejects_others():
    with (
        Session(certificate_pinning={"tls.peet.ws": ["AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="]}) as session,
        pytest.raises(TLSClientException, match="bad ssl pin") as rejected,
    ):
        session.get(PEET_API)

    # The error lists the pins the server actually presented; pinning any of them must succeed.
    presented_pin = re.search(r"found pins: \[(\S+)", str(rejected.value)).group(1)
    with Session(certificate_pinning={"tls.peet.ws": [presented_pin]}) as session:
        assert session.get(PEET_API).status_code == 200
