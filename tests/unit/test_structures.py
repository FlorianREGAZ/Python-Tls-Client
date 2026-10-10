import pytest

from tls_client.structures import CaseInsensitiveDict


@pytest.fixture
def headers() -> CaseInsensitiveDict[str]:
    return CaseInsensitiveDict({"Accept": "application/json", "User-Agent": "tls-client"})


@pytest.mark.parametrize("key", ["Accept", "accept", "ACCEPT", "aCcEpT"])
def test_lookup_ignores_case(headers, key):
    assert headers[key] == "application/json"
    assert headers.get(key) == "application/json"
    assert key in headers


def test_delete_ignores_case(headers):
    del headers["user-agent"]

    assert "User-Agent" not in headers
    assert list(headers) == ["Accept"]


def test_writing_a_key_in_another_case_replaces_the_entry_in_place(headers):
    headers["ACCEPT"] = "text/html"
    headers.update({"user-agent": "custom/1.0"})

    assert len(headers) == 2
    assert list(headers.items()) == [("ACCEPT", "text/html"), ("user-agent", "custom/1.0")]


def test_lower_items_lowercases_keys(headers):
    assert list(headers.lower_items()) == [("accept", "application/json"), ("user-agent", "tls-client")]


def test_equality_ignores_key_case_but_not_values(headers):
    assert headers == {"accept": "application/json", "USER-AGENT": "tls-client"}
    assert headers != {"accept": "text/html", "user-agent": "tls-client"}


def test_never_equal_to_a_non_mapping(headers):
    assert headers != [("Accept", "application/json"), ("User-Agent", "tls-client")]


def test_copy_is_independent_and_still_case_insensitive(headers):
    copied = headers.copy()
    copied["accept"] = "text/html"

    assert copied["ACCEPT"] == "text/html"
    assert headers["Accept"] == "application/json"


def test_accepts_pairs_and_keyword_arguments():
    built = CaseInsensitiveDict([("Accept", "*/*")], Connection="close")

    assert built == {"accept": "*/*", "connection": "close"}
