import asyncio
from asyncio import Future
from typing import Optional, Union, Any
from tls_client import Session
from tls_client.response import Response


class AsyncSession(Session):

    def execute_request(
            self,
            method: str,
            url: str,
            params: Optional[dict] = None,  # Optional[dict[str, str]]
            data: Optional[Union[str, dict]] = None,
            headers: Optional[dict] = None,  # Optional[dict[str, str]]
            cookies: Optional[dict] = None,  # Optional[dict[str, str]]
            json: Optional[dict] = None,  # Optional[dict]
            allow_redirects: Optional[bool] = False,
            insecure_skip_verify: Optional[bool] = False,
            timeout_seconds: Optional[int] = None,
            proxy: Optional[dict] = None  # Optional[dict[str, str]]
    ) -> Future[Response]:
        loop = asyncio.get_running_loop()
        return loop.run_in_executor(None, super().execute_request, method, url, params, data, headers, cookies,
                                    json, allow_redirects, insecure_skip_verify, timeout_seconds, proxy)

    def get(self, url: str, **kwargs: Any) -> Future[Response]:
        return super().get(url, **kwargs)

    def options(self, url: str, **kwargs: Any) -> Future[Response]:
        return super().options(url, **kwargs)

    def head(self, url: str, **kwargs: Any) -> Future[Response]:
        return super().head(url, **kwargs)

    def post(self, url: str, data: Optional[Union[str, dict]] = None, json: Optional[dict] = None, **kwargs: Any) -> Future[Response]:
        return super().post(url, data, json, **kwargs)

    def put(self, url: str, data: Optional[Union[str, dict]] = None, json: Optional[dict] = None, **kwargs: Any) -> Future[Response]:
        return super().put(url, data, json, **kwargs)

    def patch(self, url: str, data: Optional[Union[str, dict]] = None, json: Optional[dict] = None, **kwargs: Any) -> Future[Response]:
        return super().patch(url, data, json, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> Future[Response]:
        return super().delete(url, **kwargs)


