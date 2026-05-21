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


def test_flutter_http_codegen_emits_multipart_raw_and_binary_response_contracts(tmp_path: Path) -> None:
    bp = Blueprint(root="/api")
    with bp.group("/media") as views:
        views.POST("/preview").REQ_MULTIPART(MediaUpload).RSP_BYTES(content_type="image/jpeg")
        views.GET("/mjpeg").RSP_BYTE_STREAM(content_type="multipart/x-mixed-replace")
        views.GET("/packet").RSP_BINARY_SCHEMA(_demo_packet_schema())

    writer = FlutterWriter(tmp_path / "flutter", package="api_blueprint_example")
    writer.register(bp)
    writer.gen()

    root_dir = tmp_path / "flutter" / "lib" / "src" / "api"
    runtime = (root_dir / "runtime/gen_api_transport.dart").read_text(encoding="utf-8")
    runtime_types = (root_dir / "runtime/gen_api_types.dart").read_text(encoding="utf-8")
    route_types = (root_dir / "routes/api/media/gen_media_types.dart").read_text(encoding="utf-8")
    route_client = (root_dir / "routes/api/media/gen_media_api.dart").read_text(encoding="utf-8")
    transport = (root_dir / "transports/http/gen_http_api_transport.dart").read_text(encoding="utf-8")
    binary = (root_dir / "routes/api/media/gen_binary.dart").read_text(encoding="utf-8")

    assert "class ApiFilePart" in runtime
    assert "class ApiRawResponse" in runtime
    assert "final Object? multipart;" in runtime
    assert "Uint8List apiBlueprintReadBytes(Object? value)" in runtime
    assert "final ApiFilePart? image;" in runtime_types
    assert "multipart: multipart" in route_client
    assert 'responseKind: "bytes"' in route_client
    assert "apiBlueprintRawResponse(value, defaultContentType: \"image/jpeg\"" in route_client
    assert "decodeDemoPacket(apiBlueprintReadBytes(value))" in route_client
    assert "http.MultipartRequest(request.method, url)" in transport
    assert "http.MultipartFile.fromBytes(" in transport
    assert "ApiBinaryPayload(Uint8List.fromList(response.bodyBytes), response.headers)" in transport
    assert "DemoPacket decodeDemoPacket(Uint8List bytes)" in binary
