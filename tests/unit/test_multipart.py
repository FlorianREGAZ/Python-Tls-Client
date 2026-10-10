import base64
import io
import re
from collections.abc import Mapping

import pytest

import tls_client._multipart

URL = "https://example.com/upload"
RANDOM_BOUNDARY = tls_client._multipart.choose_boundary


def header_values(headers: Mapping[str, str], name: str) -> list[str]:
    return [value for key, value in headers.items() if key.lower() == name.lower()]


def sent_body(payload: dict) -> bytes:
    assert payload["isByteRequest"] is True
    return base64.b64decode(payload["requestBody"])


def part(disposition: str, content: bytes, *headers: str) -> bytes:
    lines = [f"Content-Disposition: form-data; {disposition}", *headers]
    return b"--BOUNDARY\r\n" + "".join(f"{line}\r\n" for line in lines).encode() + b"\r\n" + content + b"\r\n"


END = b"--BOUNDARY--\r\n"


@pytest.fixture(autouse=True)
def fixed_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tls_client._multipart, "choose_boundary", lambda: "BOUNDARY")


class TestFiles:
    def test_open_file_is_sent_under_its_basename_with_a_guessed_type(self, session, fake_lib, tmp_path):
        path = tmp_path / "report.txt"
        path.write_bytes(b"line 1\nline 2\n")

        with path.open("rb") as f:
            session.post(URL, files={"upload": f})

        assert sent_body(fake_lib.sent) == (
            part('name="upload"; filename="report.txt"', b"line 1\nline 2\n", "Content-Type: text/plain") + END
        )
        assert header_values(fake_lib.sent["headers"], "Content-Type") == ["multipart/form-data; boundary=BOUNDARY"]

    @pytest.mark.parametrize(
        "content",
        [b"caf\xc3\xa9", "café", io.BytesIO(b"caf\xc3\xa9"), io.StringIO("café")],
        ids=["bytes", "str", "binary-file", "text-file"],
    )
    def test_content_of_every_kind_is_sent_as_utf8_bytes(self, session, fake_lib, content):
        session.post(URL, files={"f": ("notes.txt", content)})

        expected = part('name="f"; filename="notes.txt"', b"caf\xc3\xa9", "Content-Type: text/plain") + END
        assert sent_body(fake_lib.sent) == expected

    def test_file_is_read_from_its_current_position(self, session, fake_lib):
        f = io.BytesIO(b"skip|keep")
        f.seek(5)

        session.post(URL, files={"f": ("a.bin", f)})

        assert b"\r\n\r\nkeep\r\n" in sent_body(fake_lib.sent)

    def test_explicit_content_type_and_extra_part_headers(self, session, fake_lib):
        session.post(
            URL,
            files={
                "typed": ("data.txt", b"{}", "application/json"),
                "extra": ("a.png", b"\x89PNG", "image/x-png", {"X-Checksum": "abc"}),
            },
        )

        assert sent_body(fake_lib.sent) == (
            part('name="typed"; filename="data.txt"', b"{}", "Content-Type: application/json")
            + part('name="extra"; filename="a.png"', b"\x89PNG", "Content-Type: image/x-png", "X-Checksum: abc")
            + END
        )

    def test_content_type_from_the_extra_headers_replaces_the_guess(self, session, fake_lib):
        session.post(URL, files={"f": ("a.txt", b"x", None, {"content-type": "text/markdown"})})

        assert sent_body(fake_lib.sent) == part('name="f"; filename="a.txt"', b"x", "content-type: text/markdown") + END

    @pytest.mark.parametrize(
        ("filename", "content_type"),
        [
            ("photo.PNG", "image/png"),
            ("blob", "application/octet-stream"),
            ("data.unknown-ext", "application/octet-stream"),
        ],
    )
    def test_content_type_is_guessed_from_the_filename(self, session, fake_lib, filename, content_type):
        session.post(URL, files={"f": (filename, b"x")})

        assert f"Content-Type: {content_type}\r\n".encode() in sent_body(fake_lib.sent)

    @pytest.mark.parametrize("name", [None, "<stdin>", 3], ids=["no-name", "pseudo-name", "descriptor"])
    def test_file_without_a_usable_name_is_sent_under_the_field_name(self, session, fake_lib, name):
        f = io.BytesIO(b"x")
        if name is not None:
            f.name = name

        session.post(URL, files={"field": f})

        assert b'name="field"; filename="field"\r\n' in sent_body(fake_lib.sent)

    def test_quotes_and_line_breaks_are_percent_escaped_and_non_ascii_is_utf8(self, session, fake_lib):
        session.post(URL, files={'a"b\r\nc': ('naïve "x".txt', b"x")})

        disposition = 'Content-Disposition: form-data; name="a%22b%0D%0Ac"; filename="naïve %22x%22.txt"\r\n'
        assert disposition.encode() in sent_body(fake_lib.sent)

    def test_none_filename_sends_a_plain_field_and_none_content_skips_it(self, session, fake_lib):
        session.post(URL, files={"plain": (None, "value"), "skipped": ("a.txt", None)})

        assert sent_body(fake_lib.sent) == part('name="plain"', b"value") + END

    def test_list_of_pairs_repeats_a_field(self, session, fake_lib):
        session.post(URL, files=[("f", ("a.txt", b"1")), ("f", ("b.txt", b"2"))])

        assert sent_body(fake_lib.sent) == (
            part('name="f"; filename="a.txt"', b"1", "Content-Type: text/plain")
            + part('name="f"; filename="b.txt"', b"2", "Content-Type: text/plain")
            + END
        )

    def test_boundary_is_random_and_matches_the_header(self, session, fake_lib, monkeypatch):
        monkeypatch.setattr(tls_client._multipart, "choose_boundary", RANDOM_BOUNDARY)

        session.post(URL, files={"f": ("a.txt", b"x")})
        session.post(URL, files={"f": ("a.txt", b"x")})

        boundaries = []
        for payload in fake_lib.payloads:
            (content_type,) = header_values(payload["headers"], "Content-Type")
            boundary = re.fullmatch(r"multipart/form-data; boundary=([0-9a-f]{32})", content_type).group(1)
            assert sent_body(payload).startswith(f"--{boundary}\r\n".encode())
            assert sent_body(payload).endswith(f"--{boundary}--\r\n".encode())
            boundaries.append(boundary)
        assert boundaries[0] != boundaries[1]

    @pytest.mark.parametrize("method", ["post", "put", "patch"])
    def test_body_verbs_take_files(self, session, fake_lib, method):
        getattr(session, method)(URL, files={"f": ("a.txt", b"x")})

        assert fake_lib.sent["requestMethod"] == method.upper()
        assert sent_body(fake_lib.sent).startswith(b"--BOUNDARY\r\n")

    def test_empty_files_fall_back_to_a_form_encoded_body(self, session, fake_lib):
        session.post(URL, data={"a": "1"}, files={})

        assert fake_lib.sent["requestBody"] == "a=1"


class TestFormFields:
    def test_data_fields_come_before_the_files(self, session, fake_lib):
        session.post(
            URL,
            data={"user": "ünï", "tags": ["x", "y"], "count": 3, "raw": b"\xff", "unset": None},
            files={"f": ("a.txt", b"x")},
        )

        assert sent_body(fake_lib.sent) == (
            part('name="user"', "ünï".encode())
            + part('name="tags"', b"x")
            + part('name="tags"', b"y")
            + part('name="count"', b"3")
            + part('name="raw"', b"\xff")
            + part('name="f"; filename="a.txt"', b"x", "Content-Type: text/plain")
            + END
        )

    def test_data_as_a_list_of_pairs_keeps_order_and_repeats(self, session, fake_lib):
        session.post(URL, data=[("a", "1"), ("b", "2"), ("a", "3")], files={"f": (None, "4")})

        assert sent_body(fake_lib.sent) == (
            part('name="a"', b"1") + part('name="b"', b"2") + part('name="a"', b"3") + part('name="f"', b"4") + END
        )


class TestContentTypeHeader:
    def test_multipart_content_type_applies_to_one_request_only(self, session, fake_lib):
        session.post(URL, files={"f": ("a.txt", b"x")})
        session.post(URL, data="raw")

        assert header_values(fake_lib.sent["headers"], "Content-Type") == []
        assert "Content-Type" not in session.headers

    def test_explicit_content_type_is_kept_like_in_requests(self, session, fake_lib):
        session.post(
            URL, files={"f": ("a.txt", b"x")}, headers={"Content-Type": "multipart/related; boundary=BOUNDARY"}
        )

        assert header_values(fake_lib.sent["headers"], "Content-Type") == ["multipart/related; boundary=BOUNDARY"]
        assert sent_body(fake_lib.sent).startswith(b"--BOUNDARY\r\n")

    def test_content_type_set_to_none_sends_none(self, session, fake_lib):
        session.post(URL, files={"f": ("a.txt", b"x")}, headers={"Content-Type": None})

        assert header_values(fake_lib.sent["headers"], "Content-Type") == []


class TestRejectedCombinations:
    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"json": {"a": 1}}, "files can't be sent with json"),
            ({"data": "a=1"}, "files can't be sent with str or bytes data"),
            ({"data": b"a=1"}, "files can't be sent with str or bytes data"),
        ],
    )
    def test_files_with_a_body_that_cannot_be_merged_raise(self, session, fake_lib, kwargs, message):
        with pytest.raises(ValueError, match=message):
            session.post(URL, files={"f": ("a.txt", b"x")}, **kwargs)

        assert fake_lib.payloads == []
