from __future__ import annotations

from .helpers import *
from api_blueprint.engine.model import Array, OneOf, LegacyStringID


def test_contract_graph_manifest_captures_rpc_and_connection_routes():
    bp = Blueprint(root="/api")
    with bp.group("/runs") as views:
        views.GET("/status").RSP(message=String(description="message"))
        views.STREAM("/events", scope=ConnectionScope.SESSION).OPEN(OpenRequest).SERVER_MESSAGE(
            "RunStreamMessage",
            state=StreamState,
            done=StreamDone,
        ).CLOSE(CloseInfo)

    graph = build_contract_graph([bp])
    manifest = graph.to_manifest()

    assert manifest["version"] == "2.0"
    assert manifest["generator"]["name"] == "api-blueprint"
    assert [service["id"] for service in manifest["services"]] == ["api.runs"]
    route_ids = [route["id"] for route in manifest["routes"]]
    assert route_ids == ["api.runs.get.status", "api.runs.stream.events"]

    status = manifest["routes"][0]
    assert status["kind"] == "rpc"
    assert status["response"]["media_type"] == "application/json"
    assert status["response"]["model"] == "RSP_Status"

    stream = manifest["routes"][1]
    assert stream["kind"] == "stream"
    assert stream["connection"]["scope"] == "session"
    assert stream["connection"]["delivery"] == "ordered"
    assert stream["connection"]["open_model"] == "OpenRequest"
    assert stream["connection"]["close_model"] == "CloseInfo"
    assert stream["connection"]["server_message"]["name"] == "RunStreamMessage"
    assert [variant["key"] for variant in stream["connection"]["server_message"]["variants"]] == ["state", "done"]

    schema = manifest["schemas"]["CloseInfo"]
    assert schema["fields"]["reason"]["optional"] is True
    assert len(manifest["hashes"]["routes"]["api.runs.stream.events"]) == 64

def test_contract_graph_manifest_captures_media_body_and_raw_response_kinds():
    bp = Blueprint(root="/api")
    with bp.group("/media") as views:
        views.POST("/preview").REQ_MULTIPART(MediaUpload).RSP_BYTES(content_type="image/jpeg")
        views.GET("/download").RSP_FILE(content_type="application/vnd.ms-excel", filename="report.xls")
        views.GET("/mjpeg").RSP_BYTE_STREAM(content_type="multipart/x-mixed-replace; boundary=frame")

    manifest = build_contract_graph([bp]).to_manifest()
    routes = {route["operation"]: route for route in manifest["routes"]}

    preview = routes["Preview"]
    assert preview["request"]["body_kind"] == "multipart"
    assert preview["request"]["multipart_model"] == "MediaUpload"
    assert preview["response"]["kind"] == "bytes"
    assert preview["response"]["content_type"] == "image/jpeg"
    assert preview["response"]["success_enveloped"] is False
    assert manifest["schemas"]["MediaUpload"]["fields"]["file"]["type"] == "file"
    assert manifest["schemas"]["MediaUpload"]["fields"]["file"]["content_types"] == ["image/jpeg"]
    assert manifest["schemas"]["MediaUpload"]["fields"]["file"]["max_size"] == 1024

    download = routes["Download"]
    assert download["response"]["kind"] == "file"
    assert download["response"]["download"] is True
    assert download["response"]["filename"] == "report.xls"
    assert "Content-Disposition" in download["response"]["headers"]

    stream = routes["Mjpeg"]
    assert stream["response"]["kind"] == "byte_stream"
    assert stream["response"]["streaming"] is True

def test_contract_graph_manifest_captures_binary_schema_request_and_response() -> None:
    request_schema = parse_binary_schema(
        """
# packet RequestPacket

endian: little
content-type: application/vnd.request-packet

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| value | u16 | 1 | min=1 | value |
        """.strip(),
        source_path="request_packet.md",
    )
    response_schema = parse_binary_schema(
        """
# packet ResponsePacket

endian: little

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| status | u8 | 1 | const=1 | status |
        """.strip(),
        source_path="response_packet.md",
    )

    bp = Blueprint(root="/api")
    with bp.group("/binary") as views:
        views.POST("/packet").REQ_BINARY_SCHEMA(request_schema).RSP_BINARY_SCHEMA(
            response_schema,
            content_type="application/vnd.response-packet",
        )

    manifest = build_contract_graph([bp]).to_manifest()
    route = manifest["routes"][0]

    assert route["request"]["body_kind"] == "binary_schema"
    assert route["request"]["binary_schema"]["name"] == "RequestPacket"
    assert route["request"]["binary_schema"]["content_type"] == "application/vnd.request-packet"
    assert route["response"]["kind"] == "binary_schema"
    assert route["response"]["content_type"] == "application/vnd.response-packet"
    assert route["response"]["binary_schema"]["name"] == "ResponsePacket"
    assert route["response"]["success_enveloped"] is False
    assert route["response"]["streaming"] is False
    assert route["response"]["download"] is False

def test_contract_graph_manifest_carries_declared_connection_delivery():
    bp = Blueprint(root="/api")
    with bp.group("/runs") as views:
        views.STREAM("/events").SERVER_MESSAGE(StreamState)
        views.CHANNEL("/chat", delivery=ConnectionDelivery.UNORDERED).SERVER_MESSAGE(StreamState).CLIENT_MESSAGE(
            StreamDone
        )

    manifest = build_contract_graph([bp]).to_manifest()
    routes = {route["id"]: route for route in manifest["routes"]}

    assert routes["api.runs.stream.events"]["connection"]["delivery"] == "ordered"
    assert routes["api.runs.channel.chat"]["connection"]["delivery"] == "unordered"

def test_contract_graph_uses_generic_field_contract_metadata():
    bp = Blueprint(root="/api")
    with bp.group("/contract") as views:
        views.POST("/submit").REQ(GenericContractPayload).RSP(message=String(description="message"))

    manifest = build_contract_graph([bp]).to_manifest()

    fields = manifest["schemas"]["GenericContractPayload"]["fields"]
    assert fields["name"]["contract"] == {"field_id": 1, "optional": True}
    assert fields["success"]["contract"] == {"field_id": 2, "choice": "result"}
    assert fields["error"]["contract"] == {"field_id": 3, "choice": "result"}
    assert "wire" not in fields["name"]
    assert "proto" not in fields["success"]


def test_contract_graph_manifest_captures_legacy_json_compat_fields():
    class LegacyPayload(Model):
        target = OneOf(String(), Array[String](), description="target")
        ids = Array[OneOf(String(), Int())](description="ids")
        normalized = Array[LegacyStringID](description="normalized")

    bp = Blueprint(root="/api")
    with bp.group("/legacy") as views:
        views.GET("/payload").RSP(LegacyPayload)

    manifest = build_contract_graph([bp]).to_manifest()
    fields = manifest["schemas"]["LegacyPayload"]["fields"]

    assert fields["target"]["type"] == "one_of"
    assert fields["target"]["variants"] == [
        {"type": "string"},
        {"type": "array", "items": {"type": "string"}},
    ]
    assert fields["ids"]["items"]["type"] == "one_of"
    assert fields["ids"]["items"]["variants"] == [{"type": "string"}, {"type": "int"}]
    assert fields["normalized"]["items"] == {
        "type": "coerce_string",
        "canonical": {"type": "string"},
        "accepts": [{"type": "string"}, {"type": "int"}],
    }
