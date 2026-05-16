from __future__ import annotations

from .transports.http.client import HttpClientTransport
from .routes.static.gen_client import StaticClient as _Route1Client


class ApiClient:
    def __init__(self, transport):
        self._transport = transport
        self.static = _Route1Client(transport)

    async def aclose(self) -> None:
        close = getattr(self._transport, "aclose", None)
        if close is not None:
            await close()

    async def __aenter__(self) -> "ApiClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()


def create_client(base_url: str = "http://localhost:2333") -> ApiClient:
    return ApiClient(HttpClientTransport(base_url))
