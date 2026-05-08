from __future__ import annotations

from typing import Any

from ....runtime.client import ApiChannelBridge, ApiClientTransport, ApiSocketBridge, ApiStreamBridge


class HelloClient:
    def __init__(self, transport: ApiClientTransport):
        self._transport = transport

    async def abc(
        self,
        query: dict[str, Any] | None = None,
    ) -> Any:
        response_type: str | None = 'RSP_Abc'
        return await self._transport.request(
            "GET",
            "/api/hello/abc",
            query=query,
            response_type=response_type,
        )

    async def map_enum(self) -> Any:
        response_type: str | None = 'RSP_MapEnum'
        return await self._transport.request(
            "GET",
            "/api/hello/map-enum",
            response_type=response_type,
        )

    async def list_enum(self) -> Any:
        response_type: str | None = 'RSP_ListEnum'
        return await self._transport.request(
            "GET",
            "/api/hello/list-enum",
            response_type=response_type,
        )

    async def string(self) -> Any:
        response_type: str | None = 'RSP_String'
        return await self._transport.request(
            "GET",
            "/api/hello/string",
            response_type=response_type,
        )

    async def uint64(self) -> Any:
        response_type: str | None = 'RSP_Uint64'
        return await self._transport.request(
            "GET",
            "/api/hello/uint64",
            response_type=response_type,
        )

    async def string_emun(self) -> Any:
        response_type: str | None = 'RSP_StringEmun'
        return await self._transport.request(
            "GET",
            "/api/hello/string-emun",
            response_type=response_type,
        )

    async def hello_way(
        self,
        query: dict[str, Any] | None = None,
    ) -> Any:
        response_type: str | None = None
        return await self._transport.request(
            "GET",
            "/api/hello/hello-way",
            query=query,
            response_type=response_type,
        )
