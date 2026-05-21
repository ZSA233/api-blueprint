from __future__ import annotations

from api_blueprint.engine.model import FileField

from .helpers import *


class MediaUpload(Model):
    title = String(description="title")
    image = FileField(content_types=["image/jpeg"], description="image")


def _demo_packet_schema():
    return parse_binary_schema(
        """
# packet DemoPacket

endian: little
content-type: application/octet-stream

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| payload | bytes | 4 | | payload |
""".strip(),
        source_path="demo_packet.md",
    )


def test_java_http_codegen_emits_multipart_raw_and_binary_response_contracts(tmp_path: Path) -> None:
    bp = Blueprint(root="/api")
    with bp.group("/media") as views:
        views.POST("/preview").REQ_MULTIPART(MediaUpload).RSP_BYTES(content_type="image/jpeg")
        views.GET("/download").RSP_FILE(content_type="application/octet-stream", filename="report.bin")
        views.GET("/mjpeg").RSP_BYTE_STREAM(content_type="multipart/x-mixed-replace")
        views.GET("/packet").RSP_BINARY_SCHEMA(_demo_packet_schema())

    client_dir = tmp_path / "client"
    server_dir = tmp_path / "server"
    client_writer = JavaClientWriter(client_dir, package="com.example.generated")
    client_writer.register(bp)
    client_writer.gen()
    server_writer = JavaServerWriter(server_dir, package="com.example.generated")
    server_writer.register(bp)
    server_writer.gen()

    package_root = Path("com/example/generated/api")
    runtime_request = (client_dir / package_root / "runtime/ApiRequest.java").read_text(encoding="utf-8")
    runtime_types = (client_dir / package_root / "runtime/ApiTypes.java").read_text(encoding="utf-8")
    runtime_file = (client_dir / package_root / "runtime/ApiFilePart.java").read_text(encoding="utf-8")
    runtime_raw = (client_dir / package_root / "runtime/ApiRawResponse.java").read_text(encoding="utf-8")
    route_types = (client_dir / package_root / "routes/api/media/MediaTypes.java").read_text(encoding="utf-8")
    route_client = (client_dir / package_root / "routes/api/media/GenMediaApi.java").read_text(encoding="utf-8")
    transport = (client_dir / package_root / "transports/http/GenJdkHttpApiTransport.java").read_text(encoding="utf-8")
    controller = (server_dir / package_root / "transports/http/api/media/GenMediaController.java").read_text(
        encoding="utf-8"
    )

    assert "public record ApiFilePart(" in runtime_file
    assert "public record ApiRawResponse(" in runtime_raw
    assert "Object multipart" in runtime_request
    assert "Function<byte[], T> binaryResponseDecoder" in runtime_request
    assert "ApiFilePart image" in runtime_types
    assert "public ApiRawResponse preview(" in route_client
    assert "public ApiStreamResponse mjpeg(" in route_client
    assert '\"binary_schema\"' in route_client
    assert "MediaTypes.DemoPacketWire::parse" in route_client
    assert "EncodedMultipart multipartBody(Object value)" in transport
    assert "new ApiRawResponse(" in transport
    assert "request.binaryResponseDecoder().apply(bodyBytes)" in transport
    assert "MultipartHttpServletRequest multipartRequest" in controller
    assert "multipartBody(multipartRequest)" in controller
    assert "rawResponse(\"file\", \"application/octet-stream\", \"report.bin\", result)" in controller
    assert "DemoPacketWire.toBinaryBody((MediaTypes.DemoPacket) result).toBytes()" in controller
