from __future__ import annotations

from typing import Any

from ...runtime.client import ApiChannelBridge, ApiClientTransport, ApiSocketBridge, ApiStreamBridge


class StaticClient:
    def __init__(self, transport: ApiClientTransport):
        self._transport = transport

    async def doc_json(self) -> Any:
        response_type: str | None = 'RSP_DocJson'
        return await self._transport.request(
            "GET",
            "/static/doc.json",
            response_type=response_type,
        )

    async def dochaha(self) -> Any:
        response_type: str | None = 'RSP_Dochaha'
        return await self._transport.request(
            "GET",
            "/static/dochaha",
            response_type=response_type,
        )
