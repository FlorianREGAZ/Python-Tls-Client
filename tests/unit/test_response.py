from typing import Any

import pytest

from tls_client.cookies import cookiejar_from_dict
from tls_client.response import build_response


def library_reply(**fields: Any) -> dict[str, Any]:
    """A reply shaped like the one the Go library returns."""
    return {"id": "response-1", "status": 200, "target": "https://example.com/", "body": "", "headers": {}, **fields}


def test_reply_fields_are_mapped_onto_the_response():
    cookies = cookiejar_from_dict({"sid": "abc"})

    response = build_response(
        library_reply(status=404, target="https://example.com/final", body='{"error": "missing"}'),
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


@pytest.mark.xfail(reason="build_response replaces the CaseInsensitiveDict with a plain dict")
def test_header_lookup_ignores_case():
    response = build_response(library_reply(headers={"Content-Type": ["text/html"]}), cookiejar_from_dict({}))

    assert response.headers["content-type"] == "text/html"
