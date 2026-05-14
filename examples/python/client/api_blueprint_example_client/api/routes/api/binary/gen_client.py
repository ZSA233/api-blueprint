from __future__ import annotations

from typing import Any

from ....runtime.client import ApiChannelBridge, ApiClientTransport, ApiSocketBridge, ApiStreamBridge

from ....runtime.binary import ApiBinaryBody
from .gen_binary import (
    DemoPacket,
    DemoPacketWire,
)


class BinaryClient:
    def __init__(self, transport: ApiClientTransport):
        self._transport = transport

    async def packet(
        self,
        query: dict[str, Any] | None = None,
        binary: DemoPacket | ApiBinaryBody = ...,
    ) -> Any:
        response_type: str | None = 'RSP_Packet'
        return await self._transport.request(
            "POST",
            "/api/binary/packet",
            query=query,
            binary=DemoPacketWire.to_binary_body(binary),
            response_type=response_type,
        )
