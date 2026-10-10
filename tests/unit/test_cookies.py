import pickle

import pytest

from tls_client.cookies import (
    CookieConflictError,
    RequestsCookieJar,
    cookiejar_from_dict,
    create_cookie,
    extract_cookies_to_jar,
    merge_cookies,
)


class TestRequestsCookieJar:
    def test_dict_style_access(self):
        jar = RequestsCookieJar()
        jar["a"] = "1"
        jar.set("b", "2")

        assert jar["a"] == "1"
        assert dict(jar) == {"a": "1", "b": "2"}

        del jar["a"]

        assert "a" not in jar
        assert jar.get("a") is None
        assert jar.get("a", "fallback") == "fallback"

    def test_assigning_none_removes_the_cookie(self):
        jar = cookiejar_from_dict({"a": "1", "b": "2"})

        jar["a"] = None

        assert dict(jar) == {"b": "2"}

    def test_same_name_on_two_domains_must_be_disambiguated(self):
        jar = RequestsCookieJar()
        jar.set("token", "for-a", domain="a.example")
        jar.set("token", "for-b", domain="b.example")

        with pytest.raises(CookieConflictError):
            jar["token"]
        assert "token" in jar
        assert jar.get("token", domain="b.example") == "for-b"

    def test_same_name_on_two_paths_must_be_disambiguated(self):
        jar = RequestsCookieJar()
        jar.set("id", "root", path="/")
        jar.set("id", "api", path="/api")

        with pytest.raises(CookieConflictError):
            jar["id"]
        assert jar.get("id", path="/api") == "api"

    @pytest.mark.xfail(reason="_find_no_duplicates treats an empty value as a missing cookie")
    def test_cookie_with_empty_value_is_readable(self):
        jar = cookiejar_from_dict({"consent": ""})

        assert jar["consent"] == ""
        assert dict(jar) == {"consent": ""}

    def test_get_dict_filters_by_domain_and_path(self):
        jar = RequestsCookieJar()
        jar.set("a", "1", domain="a.example", path="/")
        jar.set("b", "2", domain="a.example", path="/api")
        jar.set("c", "3", domain="b.example", path="/")

        assert jar.get_dict(domain="a.example") == {"a": "1", "b": "2"}
        assert jar.get_dict(path="/") == {"a": "1", "c": "3"}
        assert jar.get_dict(domain="a.example", path="/api") == {"b": "2"}

    def test_list_domains_and_paths_are_deduplicated(self):
        jar = RequestsCookieJar()
        jar.set("a", "1", domain="a.example", path="/")
        jar.set("b", "2", domain="a.example", path="/api")
        jar.set("c", "3", domain="b.example", path="/")

        assert sorted(jar.list_domains()) == ["a.example", "b.example"]
        assert sorted(jar.list_paths()) == ["/", "/api"]

    @pytest.mark.xfail(reason="multiple_domains() looks for a repeated domain instead of a second distinct one")
    def test_multiple_domains(self):
        jar = RequestsCookieJar()
        jar.set("a", "1", domain="a.example")
        jar.set("b", "2", domain="a.example")
        assert not jar.multiple_domains()

        jar.set("c", "3", domain="b.example")
        assert jar.multiple_domains()

    def test_copy_does_not_share_cookies(self):
        jar = cookiejar_from_dict({"a": "1"})

        copied = jar.copy()
        copied["a"] = "changed"
        copied["b"] = "2"

        assert dict(jar) == {"a": "1"}
        assert copied.get_policy() is jar.get_policy()

    def test_update_from_another_jar_copies_the_cookie_objects(self):
        source = RequestsCookieJar()
        source.set("a", "1", domain="a.example")
        jar = RequestsCookieJar()

        jar.update(source)
        next(iter(jar)).value = "changed"

        assert source.get("a", domain="a.example") == "1"
        assert jar.get("a", domain="a.example") == "changed"

    def test_survives_pickling_and_stays_writable(self):
        jar = RequestsCookieJar()
        jar.set("a", "1", domain="a.example")

        restored = pickle.loads(pickle.dumps(jar))
        restored.set("b", "2")

        assert restored.get("a", domain="a.example") == "1"
        assert dict(restored) == {"a": "1", "b": "2"}


class TestCreateCookie:
    def test_rejects_unknown_attributes(self):
        with pytest.raises(TypeError, match="domian"):
            create_cookie("a", "1", domian="example.com")

    def test_derives_specified_flags_from_given_attributes(self):
        cookie = create_cookie("a", "1", domain=".example.com", port="443")

        assert cookie.domain_specified
        assert cookie.domain_initial_dot
        assert cookie.port_specified

    def test_defaults_to_a_host_only_session_cookie_on_root_path(self):
        cookie = create_cookie("a", "1")

        assert not cookie.domain_specified
        assert cookie.path == "/"
        assert cookie.expires is None


def test_merge_cookies_overrides_cookies_with_the_same_name():
    jar = cookiejar_from_dict({"token": "old", "keep": "1"})

    merged = merge_cookies(jar, {"token": "new"})

    assert dict(merged) == {"token": "new", "keep": "1"}


class TestExtractCookiesToJar:
    def test_every_set_cookie_header_is_extracted_and_merged_into_the_session_jar(self):
        session_jar = cookiejar_from_dict({"existing": "1"})

        response_jar = extract_cookies_to_jar(
            request_url="https://example.com/login",
            request_headers={},
            cookie_jar=session_jar,
            response_headers={"Set-Cookie": ["a=1; Path=/", "b=2; Path=/; HttpOnly"]},
        )

        assert dict(response_jar) == {"a": "1", "b": "2"}
        assert dict(session_jar) == {"existing": "1", "a": "1", "b": "2"}

    def test_cookie_without_domain_is_scoped_to_the_request_host(self):
        response_jar = extract_cookies_to_jar(
            request_url="https://example.com/",
            request_headers={},
            cookie_jar=RequestsCookieJar(),
            response_headers={"Set-Cookie": ["a=1"]},
        )

        assert response_jar.list_domains() == ["example.com"]

    def test_host_header_decides_the_cookie_domain(self):
        response_jar = extract_cookies_to_jar(
            request_url="https://203.0.113.7/",
            request_headers={"Host": "example.com"},
            cookie_jar=RequestsCookieJar(),
            response_headers={"Set-Cookie": ["a=1"]},
        )

        assert response_jar.list_domains() == ["example.com"]

    def test_cookie_for_a_foreign_domain_is_rejected(self):
        session_jar = RequestsCookieJar()

        response_jar = extract_cookies_to_jar(
            request_url="https://example.com/",
            request_headers={},
            cookie_jar=session_jar,
            response_headers={"Set-Cookie": ["a=1; Domain=attacker.example"]},
        )

        assert len(response_jar) == 0
        assert len(session_jar) == 0

    def test_server_can_delete_a_session_cookie(self):
        session_jar = RequestsCookieJar()
        extract_cookies_to_jar("https://example.com/", {}, session_jar, {"Set-Cookie": ["sid=abc; Path=/"]})
        assert "sid" in session_jar

        extract_cookies_to_jar(
            "https://example.com/",
            {},
            session_jar,
            {"Set-Cookie": ["sid=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT"]},
        )

        assert "sid" not in session_jar
