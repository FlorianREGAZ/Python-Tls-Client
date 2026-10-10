import base64
import os
import tracemalloc
from typing import Any

import pytest

from tls_client.cookies import cookiejar_from_dict
from tls_client.response import build_response


def data_uri(body: bytes, mime_type: str = "text/plain; charset=utf-8") -> str:
    """A body the way the Go library returns it for isByteResponse requests; it sniffs the mime type itself."""
    return f"data:{mime_type};base64,{base64.b64encode(body).decode()}"


def library_reply(**fields: Any) -> dict[str, Any]:
    """A reply shaped like the one the Go library returns."""
    return {
        "id": "response-1",
        "status": 200,
        "target": "https://example.com/",
        "body": data_uri(b""),
        "headers": {},
        **fields,
    }


def test_reply_fields_are_mapped_onto_the_response():
    cookies = cookiejar_from_dict({"sid": "abc"})

    response = build_response(
        library_reply(status=404, target="https://example.com/final", body=data_uri(b'{"error": "missing"}')),
        cookies,
    )

    assert response.status_code == 404
    assert response.url == "https://example.com/final"
    assert response.json() == {"error": "missing"}
    assert response.cookies is cookies


def test_single_header_values_are_unwrapped_and_repeated_ones_stay_lists():
    response = build_response(
        library_reply(headers={"Content-Type": ["text/html"], "Vary": ["Accept", "Origin"]}),
        cookiejar_from_dict({}),
    )

    assert response.headers == {"Content-Type": "text/html", "Vary": ["Accept", "Origin"]}


def test_null_headers_become_an_empty_mapping():
    response = build_response(library_reply(headers=None), cookiejar_from_dict({}))

    assert dict(response.headers) == {}


@pytest.mark.parametrize("name", ["Content-Type", "content-type", "CONTENT-TYPE"])
def test_header_lookup_ignores_case(name):
    response = build_response(library_reply(headers={"Content-Type": ["text/html"]}), cookiejar_from_dict({}))

    assert response.headers[name] == "text/html"
    assert response.headers.get(name) == "text/html"
    assert name in response.headers


class TestBody:
    def test_binary_body_is_decoded_byte_for_byte(self):
        body = bytes(range(256))

        response = build_response(
            library_reply(body=data_uri(body, "application/octet-stream")), cookiejar_from_dict({})
        )

        assert response.content == body

    def test_empty_body(self):
        response = build_response(library_reply(), cookiejar_from_dict({}))

        assert response.content == b""
        assert response.text == ""

    def test_text_uses_the_charset_from_the_content_type_header(self):
        # The library labels the data URI with a sniffed type; only the header names the real charset.
        response = build_response(
            library_reply(
                body=data_uri("café".encode("latin-1")),
                headers={"content-type": ['text/plain; Charset="ISO-8859-1"']},
            ),
            cookiejar_from_dict({}),
        )

        assert response.encoding == "ISO-8859-1"
        assert response.text == "café"

    def test_text_defaults_to_utf8_and_replaces_undecodable_bytes(self):
        response = build_response(
            library_reply(body=data_uri("∮ ok ".encode() + b"\xff"), headers={"Content-Type": ["text/plain"]}),
            cookiejar_from_dict({}),
        )

        assert response.encoding is None
        assert response.text == "∮ ok �"

    def test_unknown_charset_falls_back_to_utf8(self):
        response = build_response(
            library_reply(body=data_uri("é".encode()), headers={"Content-Type": ["text/plain; charset=made-up"]}),
            cookiejar_from_dict({}),
        )

        assert response.text == "é"

    def test_text_follows_an_encoding_set_by_the_caller(self):
        response = build_response(library_reply(body=data_uri("café".encode("cp1252"))), cookiejar_from_dict({}))

        response.encoding = "cp1252"

        assert response.text == "café"

    def test_body_that_is_not_a_data_uri_is_taken_as_text(self):
        response = build_response(library_reply(body='{"plain": true}'), cookiejar_from_dict({}))

        assert response.json() == {"plain": True}

    def test_large_body_is_not_held_in_several_copies_at_once(self):
        body = os.urandom(8_000_000)
        tracemalloc.start()
        try:
            reply = library_reply(body=data_uri(body))
            tracemalloc.reset_peak()
            response = build_response(reply, cookiejar_from_dict({}))
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        assert response.content == body
        assert "body" not in reply
        # The data URI and its payload are each 4/3 of the body. Freeing the data URI before decoding keeps the
        # peak near 8/3 of the body; holding it, the payload and the decoded bytes together would reach 11/3.
        assert peak < 3 * len(body)
