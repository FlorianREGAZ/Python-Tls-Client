import asyncio
import copy
import functools
from collections.abc import Callable
from concurrent.futures import Executor
from typing import Any, TypeVar

from .cookies import RequestsCookieJar
from .response import Response
from .sessions import Session, _Data, _Json, _Proxy
from .structures import CaseInsensitiveDict

_T = TypeVar("_T")


class AsyncSession:
    """asyncio front end for :class:`Session`.

    Takes the same arguments as ``Session`` and runs each request in a worker thread, so requests on one session can
    run concurrently. Use it from a single event loop.
    """

    def __init__(self, *args: Any, executor: Executor | None = None, **kwargs: Any) -> None:
        self._session = Session(*args, **kwargs)
        # Runs the blocking calls; None means the event loop's default thread pool, whose size limits how many requests
        # run at once.
        self._executor = executor

    # --- Session state ------------------------------------------------------------------------------------------------
    # Changes apply to requests started afterwards. Requests that are already running keep what they started with.

    @property
    def session(self) -> Session:
        """The wrapped Session, for the settings that have no property here."""
        return self._session

    @property
    def headers(self) -> CaseInsensitiveDict[str]:
        return self._session.headers

    @headers.setter
    def headers(self, value: CaseInsensitiveDict[str]) -> None:
        self._session.headers = value

    @property
    def cookies(self) -> RequestsCookieJar:
        return self._session.cookies

    @cookies.setter
    def cookies(self, value: RequestsCookieJar) -> None:
        self._session.cookies = value

    @property
    def proxies(self) -> _Proxy:
        return self._session.proxies

    @proxies.setter
    def proxies(self, value: _Proxy) -> None:
        self._session.proxies = value

    @property
    def params(self) -> dict[str, Any]:
        return self._session.params

    @params.setter
    def params(self, value: dict[str, Any]) -> None:
        self._session.params = value

    @property
    def timeout_seconds(self) -> float:
        return self._session.timeout_seconds

    @timeout_seconds.setter
    def timeout_seconds(self, value: float) -> None:
        self._session.timeout_seconds = value

    # --- Lifecycle ----------------------------------------------------------------------------------------------------

    async def __aenter__(self) -> "AsyncSession":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def close(self) -> str:
        """Frees the native session. Await any running requests first."""
        return await self._run(self._session.close)

    # --- Requests -----------------------------------------------------------------------------------------------------

    async def execute_request(self, method: str, url: str, **kwargs: Any) -> Response:
        # Session.execute_request reads the session's headers and writes to its cookie jar, and neither is safe to use
        # from several threads at once. Each request therefore runs on a shallow copy of the session: it shares the
        # native session, so connections are reused, but gets its own headers and cookie jar.
        request_session = copy.copy(self._session)
        request_session.headers = CaseInsensitiveDict(self._session.headers)
        request_session.cookies = self._session.cookies.copy()

        response = await self._run(request_session.execute_request, method=method, url=url, **kwargs)

        # Back on the event loop thread, so no other request touches the jar while the new cookies go in. Like Session,
        # keep the cookies sent with the request, then the ones the server set (response.cookies holds those of every
        # redirect followed too).
        cookies = kwargs.get("cookies")
        if cookies:
            self._session.cookies.update(cookies)
        self._session.cookies.update(response.cookies)
        return response

    async def get(self, url: str, **kwargs: Any) -> Response:
        """Sends a GET request"""
        return await self.execute_request(method="GET", url=url, **kwargs)

    async def options(self, url: str, **kwargs: Any) -> Response:
        """Sends a OPTIONS request"""
        return await self.execute_request(method="OPTIONS", url=url, **kwargs)

    async def head(self, url: str, **kwargs: Any) -> Response:
        """Sends a HEAD request"""
        return await self.execute_request(method="HEAD", url=url, **kwargs)

    async def post(self, url: str, data: _Data | None = None, json: _Json | None = None, **kwargs: Any) -> Response:
        """Sends a POST request"""
        return await self.execute_request(method="POST", url=url, data=data, json=json, **kwargs)

    async def put(self, url: str, data: _Data | None = None, json: _Json | None = None, **kwargs: Any) -> Response:
        """Sends a PUT request"""
        return await self.execute_request(method="PUT", url=url, data=data, json=json, **kwargs)

    async def patch(self, url: str, data: _Data | None = None, json: _Json | None = None, **kwargs: Any) -> Response:
        """Sends a PATCH request"""
        return await self.execute_request(method="PATCH", url=url, data=data, json=json, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> Response:
        """Sends a DELETE request"""
        return await self.execute_request(method="DELETE", url=url, **kwargs)

    async def _run(self, func: Callable[..., _T], /, *args: Any, **kwargs: Any) -> _T:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, functools.partial(func, *args, **kwargs))
