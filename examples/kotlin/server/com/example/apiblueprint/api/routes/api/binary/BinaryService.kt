package com.example.apiblueprint.api.routes.api.binary

import com.example.apiblueprint.api.runtime.*

import com.example.apiblueprint.api.runtime.binary.ApiBinaryBody

public class BinaryService : BinaryServiceStub() {

    /**
     * Binary packet example
     * POST /api/binary/packet
     */
    public override suspend fun packet(
        query: BinaryPacketQuery,
        binary: DemoPacket
    ): BinaryPacketResponse {
        return super.packet(
            query = query,
            binary = binary
        )
    }

    /**
     * Binary audit packet example
     * POST /api/binary/audit-packet
     */
    public override suspend fun auditPacket(
        query: BinaryAuditPacketQuery,
        binary: AuditPacket
    ): BinaryAuditPacketResponse {
        return super.auditPacket(
            query = query,
            binary = binary
        )
    }

    /**
     * Wide integer binary packet example
     * POST /api/binary/wide-packet
     */
    public override suspend fun widePacket(
        query: BinaryWidePacketQuery,
        binary: WidePacket
    ): BinaryWidePacketResponse {
        return super.widePacket(
            query = query,
            binary = binary
        )
    }

    /**
     * Binary audit packet response example
     * GET /api/binary/audit-packet-response
     */
    public override suspend fun auditPacketResponse(
    ): AuditPacket {
        return super.auditPacketResponse(
        )
    }

}
