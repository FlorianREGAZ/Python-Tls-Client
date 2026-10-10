import asyncio
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

import pytest

from tls_client import AsyncSession
from tls_client.cookies import cookiejar_from_dict
from tls_client.exceptions import TLSClientException
from tls_client.structures import CaseInsensitiveDict

URL = "https://example.com/path"


def sent_cookies(payload: dict) -> dict[str, str]:
    """Cookies of the Cookie header the request was sent with."""
    header = payload["headers"].get("Cookie", "")
    return dict(pair.split("=", 1) for pair in header.split("; ") if pair)


class CountingExecutor(ThreadPoolExecutor):
    def __init__(self) -> None:
        super().__init__(max_workers=1)
        self.submitted = 0

    def submit(self, fn: Any, /, *args: Any, **kwargs: Any) -> Future:
        self.submitted += 1
        return super().submit(fn, *args, **kwargs)


class TestSettings:
    def test_constructor_arguments_are_forwarded_to_the_session(self, fake_lib):
        async def main():
            async with AsyncSession("firefox_120", random_tls_extension_order=True) as session:
                await session.get(URL)

        asyncio.run(main())

        assert fake_lib.sent["tlsClientIdentifier"] == "firefox_120"
        assert fake_lib.sent["withRandomTLSExtensionOrder"] is True

    def test_properties_read_and_write_the_wrapped_session(self, fake_lib):
        session = AsyncSession()
        jar = cookiejar_from_dict({"a": "1"})

        session.headers = CaseInsensitiveDict({"X-Test": "1"})
        session.cookies = jar
        session.proxies = "http://proxy:8080"
        session.params = {"q": "1"}
        session.timeout_seconds = 5

        assert session.session.headers == {"X-Test": "1"}
        assert session.session.cookies is jar
        assert session.session.proxies == "http://proxy:8080"
        assert session.session.params == {"q": "1"}
        assert session.session.timeout_seconds == 5
        assert session.headers is session.session.headers
        assert session.cookies is jar
        assert session.proxies == "http://proxy:8080"
        assert session.params == {"q": "1"}
        assert session.timeout_seconds == 5

    def test_session_settings_are_sent(self, fake_lib):
        async def main():
            async with AsyncSession() as session:
                session.headers["X-Session"] = "1"
                session.cookies.set("from_session", "1")
                session.proxies = "http://proxy:8080"
                session.timeout_seconds = 5
                session.session.force_http1 = True
                await session.get(URL)

        asyncio.run(main())

        assert fake_lib.sent["headers"]["X-Session"] == "1"
        assert sent_cookies(fake_lib.sent) == {"from_session": "1"}
        assert fake_lib.sent["proxyUrl"] == "http://proxy:8080"
        assert fake_lib.sent["timeoutMilliseconds"] == 5000
        assert fake_lib.sent["forceHttp1"] is True


class TestRequests:
    @pytest.mark.parametrize("method", ["GET", "OPTIONS", "HEAD", "POST", "PUT", "PATCH", "DELETE"])
    def test_verb_helper_sends_its_method(self, fake_lib, method):
        async def main():
            async with AsyncSession() as session:
                return await getattr(session, method.lower())(URL)

        response = asyncio.run(main())

        assert fake_lib.sent["requestMethod"] == method
        assert response.status_code == 200

    @pytest.mark.parametrize("method", ["post", "put", "patch"])
    def test_body_verbs_take_data_as_second_positional_argument(self, fake_lib, method):
        async def main():
            async with AsyncSession() as session:
                await getattr(session, method)(URL, "raw")

        asyncio.run(main())

        assert fake_lib.sent["requestBody"] == "raw"

    def test_keyword_arguments_are_forwarded(self, fake_lib):
        fake_lib.reply_with(status=302, headers={"Location": ["/next"]})

        async def main():
            async with AsyncSession() as session:
                await session.execute_request("GET", URL, params={"q": "1"}, allow_redirects=True)

        asyncio.run(main())

        assert [payload["requestUrl"] for payload in fake_lib.payloads] == [f"{URL}?q=1", "https://example.com/next"]

    def test_requests_use_the_native_session_of_the_wrapped_session(self, fake_lib):
        async def main():
            async with AsyncSession() as session:
                await asyncio.gather(session.get(URL), session.get(URL))

        asyncio.run(main())

        session_ids = {payload["sessionId"] for payload in fake_lib.payloads}
        assert session_ids == set(fake_lib.destroyed_session_ids)
        assert len(session_ids) == 1

    def test_library_error_is_raised_as_tls_client_exception(self, fake_lib):
        fake_lib.reply_with(status=0, body="connection refused", headers={"Set-Cookie": ["a=1; Path=/"]})

        async def main():
            async with AsyncSession() as session:
                with pytest.raises(TLSClientException, match="connection refused"):
                    await session.get(URL)
                return session

        assert len(asyncio.run(main()).cookies) == 0

    def test_requests_run_on_the_given_executor(self, fake_lib):
        with CountingExecutor() as executor:

            async def main():
                async with AsyncSession(executor=executor) as session:
                    await session.get(URL)
                    await session.post(URL)

            asyncio.run(main())

        # Two requests, then close.
        assert executor.submitted == 3


class TestState:
    def test_cookies_from_the_response_are_kept_for_the_next_request(self, fake_lib):
        fake_lib.reply_with(headers={"Set-Cookie": ["a=1; Path=/", "b=2; Path=/"]})

        async def main():
            async with AsyncSession() as session:
                response = await session.get(URL)
                await session.get(URL)
                return session, response

        session, response = asyncio.run(main())

        assert dict(response.cookies) == {"a": "1", "b": "2"}
        assert dict(session.cookies) == {"a": "1", "b": "2"}
        assert sent_cookies(fake_lib.sent) == {"a": "1", "b": "2"}

    def test_cookies_set_on_every_redirect_hop_end_up_in_the_jar(self, fake_lib):
        fake_lib.reply_with(status=302, headers={"Location": ["/second"], "Set-Cookie": ["a=1; Path=/"]})
        fake_lib.reply_with(status=307, headers={"Location": ["/third"], "Set-Cookie": ["b=2; Path=/"]})
        fake_lib.reply_with(headers={"Set-Cookie": ["c=3; Path=/"]})

        async def main():
            async with AsyncSession() as session:
                response = await session.get(URL, allow_redirects=True)
                await session.get(URL)
                return session, response

        session, response = asyncio.run(main())

        assert len(response.history) == 2
        assert dict(session.cookies) == {"a": "1", "b": "2", "c": "3"}
        assert sent_cookies(fake_lib.payloads[2]) == {"a": "1", "b": "2"}
        assert sent_cookies(fake_lib.sent) == {"a": "1", "b": "2", "c": "3"}

    def test_cleared_cookies_are_not_sent(self, fake_lib):
        fake_lib.reply_with(headers={"Set-Cookie": ["a=1; Path=/"]})

        async def main():
            async with AsyncSession() as session:
                await session.get(URL)
                session.cookies.clear()
                await session.get(URL)

        asyncio.run(main())

        assert sent_cookies(fake_lib.sent) == {}

    @pytest.mark.parametrize("cookies", [{"from_request": "2"}, cookiejar_from_dict({"from_request": "2"})])
    def test_request_cookies_are_kept_in_the_jar_like_session_does(self, fake_lib, cookies):
        async def main():
            async with AsyncSession() as session:
                session.cookies.set("from_session", "1")
                await session.get(URL, cookies=cookies)
                return session

        session = asyncio.run(main())

        assert sent_cookies(fake_lib.sent) == {"from_session": "1", "from_request": "2"}
        assert dict(session.cookies) == {"from_session": "1", "from_request": "2"}

    def test_inferred_content_type_applies_to_one_request_only(self, fake_lib):
        async def main():
            async with AsyncSession() as session:
                await session.post(URL, json={"a": 1})
                await session.post(URL, data={"a": "1"})
                return session

        session = asyncio.run(main())

        assert fake_lib.payloads[0]["headers"]["Content-Type"] == "application/json"
        assert fake_lib.payloads[1]["headers"]["Content-Type"] == "application/x-www-form-urlencoded"
        assert "Content-Type" not in session.headers

    def test_request_headers_leave_session_headers_untouched(self, fake_lib):
        async def main():
            async with AsyncSession() as session:
                before = session.headers.copy()
                await session.get(URL, headers={"X-Request": "1", "Accept": None})
                return before, session.headers

        before, after = asyncio.run(main())

        assert after == before


class TestLifecycle:
    def test_close_destroys_the_native_session(self, fake_lib):
        async def main():
            session = AsyncSession()
            await session.get(URL)
            return await session.close()

        result = asyncio.run(main())

        assert fake_lib.destroyed_session_ids == [fake_lib.sent["sessionId"]]
        assert f"destroy-{fake_lib.sent['sessionId']}" in fake_lib.freed_ids
        assert '"success": true' in result

    def test_leaving_the_async_with_block_closes_the_session_even_on_error(self, fake_lib):
        async def main():
            async with AsyncSession():
                raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            asyncio.run(main())

        assert len(fake_lib.destroyed_session_ids) == 1
