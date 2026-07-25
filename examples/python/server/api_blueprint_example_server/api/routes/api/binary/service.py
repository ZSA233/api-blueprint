from __future__ import annotations

from .gen_service import *
from .gen_types import *


class BinaryServiceImpl(BinaryServiceStub):
    async def packet(
        self,
        query: PacketQuery,
        binary: DemoPacket,
    ) -> PacketResponse:
        """Binary packet example
        POST /api/binary/packet
        """
        return await super().packet(
            query=query,
            binary=binary,
        )

    async def audit_packet(
        self,
        query: AuditPacketQuery,
        binary: AuditPacket,
    ) -> AuditPacketResponse:
        """Binary audit packet example
        POST /api/binary/audit-packet
        """
        return await super().audit_packet(
            query=query,
            binary=binary,
        )

    async def wide_packet(
        self,
        query: WidePacketQuery,
        binary: WidePacket,
    ) -> WidePacketResponse:
        """Wide integer binary packet example
        POST /api/binary/wide-packet
        """
        return await super().wide_packet(
            query=query,
            binary=binary,
        )

    async def audit_packet_response(self) -> AuditPacket:
        """Binary audit packet response example
        GET /api/binary/audit-packet-response
        """
        return await super().audit_packet_response()
