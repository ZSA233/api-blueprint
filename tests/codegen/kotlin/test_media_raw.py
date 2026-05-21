from __future__ import annotations

from pathlib import Path

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


def test_kotlin_http_codegen_emits_multipart_raw_and_binary_response_contracts(tmp_path) -> None:
    bp = Blueprint(root="/api")
    with bp.group("/media") as views:
        views.POST("/preview").REQ_MULTIPART(MediaUpload).RSP_BYTES(content_type="image/jpeg")
        views.GET("/mjpeg").RSP_BYTE_STREAM(content_type="multipart/x-mixed-replace")
        views.GET("/packet").RSP_BINARY_SCHEMA(_demo_packet_schema())

    client_dir = tmp_path / "client"
    server_dir = tmp_path / "server"
    client_writer = KotlinWriter(client_dir, package="com.example.generated")
    client_writer.register(bp)
    client_writer.gen()
    server_writer = KotlinServerWriter(server_dir, package="com.example.generated")
    server_writer.register(bp)
    server_writer.gen()

    package_root = Path("com/example/generated/api")
    runtime = (client_dir / package_root / "runtime/GenApiTransport.kt").read_text(encoding="utf-8")
    runtime_types = (client_dir / package_root / "runtime/GenApiTypes.kt").read_text(encoding="utf-8")
    binary_runtime = (client_dir / package_root / "runtime/binary/GenBinaryRuntime.kt").read_text(encoding="utf-8")
    route_types = (client_dir / package_root / "routes/api/media/GenMediaTypes.kt").read_text(encoding="utf-8")
    route_client = (client_dir / package_root / "routes/api/media/GenMediaApi.kt").read_text(encoding="utf-8")
    transport = (client_dir / package_root / "transports/http/GenOkHttpApiTransport.kt").read_text(encoding="utf-8")
    ktor = (server_dir / package_root / "transports/ktor/api/media/GenMediaKtorRoutes.kt").read_text(
        encoding="utf-8"
    )

    assert "public data class ApiFilePart(" in runtime
    assert "public data class ApiRawResponse(" in runtime
    assert "public val multipart: Any? = null" in runtime
    assert "public val responseDecoder: ((ApiResponse) -> T)? = null" in runtime
    assert "public class BinaryReader" in binary_runtime
    assert "public fun parse(bytes: ByteArray): DemoPacket" in route_types
    assert "public val image: ApiFilePart" in runtime_types
    assert "multipartSerializer = MediaUpload.serializer()" in route_client
    assert 'responseDecoder = { response -> response.toRawResponse("image/jpeg", "") }' in route_client
    assert "responseDecoder = { response -> DemoPacketWire.parse(response.body) }" in route_client
    assert "MultipartBody.Builder().setType(MultipartBody.FORM)" in transport
    assert "file.bytes.toRequestBody(file.contentType.toMediaType())" in transport
    assert "decodeMultipart(call, MediaUpload.serializer())" in ktor
    assert "JsonArray(bytes.map { JsonPrimitive(it.toInt()) })" in ktor
    assert "JsonPrimitive(it.toInt() and 0xFF)" not in ktor
    assert "respondRaw(call, result, \"bytes\", \"image/jpeg\", \"\")" in ktor
    assert "DemoPacketWire.toBinaryBody(result).toByteArray()" in ktor
