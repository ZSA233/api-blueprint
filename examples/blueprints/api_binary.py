from api_blueprint.includes import *

from blueprints.app import apibp


with apibp.group("/binary") as views:
    views.POST("/packet", summary="Binary packet example").ARGS(
        trace=String(description="trace id", omitempty=True),
    ).REQ_BINARY("./binary/demo_packet.md").RSP(
        trace=String(description="trace id"),
        version=Uint(description="packet version"),
        item_count=Uint(description="item count"),
        payload=String(description="payload"),
        score_sum=Float64(description="score sum"),
        first_label=String(description="first item label"),
        item_ids=Array[Uint](description="item ids"),
        checksum=Uint(description="checksum"),
    )
    views.POST("/audit-packet", summary="Binary audit packet example").ARGS(
        trace=String(description="trace id", omitempty=True),
    ).REQ_BINARY("./binary/audit_packet.md").RSP(
        trace=String(description="trace id"),
        item_count=Uint(description="item count"),
        checksum=Uint(description="checksum"),
    )
    views.GET(
        "/audit-packet-response",
        operation_id="auditPacketResponse",
        summary="Binary audit packet response example",
    ).RSP_BINARY_SCHEMA("./binary/audit_packet.md")
