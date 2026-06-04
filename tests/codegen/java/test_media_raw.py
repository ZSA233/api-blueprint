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
    runtime_request = (client_dir / package_root / "runtime/GenApiRequest.java").read_text(encoding="utf-8")
    runtime_body_spec = (client_dir / package_root / "runtime/GenApiRequestBodySpec.java").read_text(encoding="utf-8")
    runtime_response_spec = (client_dir / package_root / "runtime/GenApiResponseSpec.java").read_text(encoding="utf-8")
    runtime_types = (client_dir / package_root / "runtime/GenApiTypes.java").read_text(encoding="utf-8")
    runtime_file = (client_dir / package_root / "runtime/GenApiFilePart.java").read_text(encoding="utf-8")
    runtime_raw = (client_dir / package_root / "runtime/GenApiRawResponse.java").read_text(encoding="utf-8")
    runtime_stream = (client_dir / package_root / "runtime/GenApiStreamResponse.java").read_text(encoding="utf-8")
    route_types = (client_dir / package_root / "routes/api/media/GenMediaTypes.java").read_text(encoding="utf-8")
    route_client = (client_dir / package_root / "routes/api/media/GenMediaApi.java").read_text(encoding="utf-8")
    transport = (client_dir / package_root / "transports/http/GenJdkHttpApiTransport.java").read_text(encoding="utf-8")
    server_types = (server_dir / package_root / "types/api/media/GenMediaTypes.java").read_text(encoding="utf-8")
    preview_annotation = (server_dir / package_root / "annotations/api/media/GenPreview.java").read_text(
        encoding="utf-8"
    )
    spring_assertions = (server_dir / package_root / "spring/GenSpringMvcContractAssertions.java").read_text(
        encoding="utf-8"
    )

    assert "public final class GenApiFilePart implements AutoCloseable" in runtime_file
    assert "InputStream body" in runtime_file
    assert "public static GenApiFilePart ofStream" in runtime_file
    assert "public byte[] readAllBytes() throws IOException" in runtime_file
    assert "public record GenApiRawResponse(" in runtime_raw
    assert "public record GenApiStreamResponse(" in runtime_stream
    assert "InputStream body" in runtime_stream
    assert ") implements AutoCloseable" in runtime_stream
    assert "public byte[] readAllBytes() throws IOException" in runtime_stream
    assert "new ByteArrayInputStream(bytes)" in runtime_stream
    assert "GenApiRequestBodySpec body" in runtime_request
    assert "GenApiResponseSpec<T> response" in runtime_request
    assert "Object multipart" in runtime_body_spec
    assert "Function<byte[], T> binaryDecoder" in runtime_response_spec
    assert "String responseFilename" not in runtime_request
    assert "GenApiFilePart image" in runtime_types
    assert "public GenApiRawResponse preview(" in route_client
    assert "public GenApiStreamResponse mjpeg(" in route_client
    assert '\"binary_schema\"' in route_client
    assert "GenMediaTypes.DemoPacketWire::parse" in route_client
    assert "EncodedMultipart multipartBody(Object value)" in transport
    assert "HttpRequest.BodyPublishers.ofInputStream" in transport
    assert "parts.add(file::body)" in transport
    assert "new GenApiRawResponse(" in transport
    assert "HttpResponse.BodyHandlers.ofInputStream()" in transport
    assert "new GenApiStreamResponse(\n                response.body()," in transport
    assert "decodeRawApiError(request.routeId(), body, responseSpec.envelope())" in transport
    assert "private Optional<GenApiError> decodeRawApiError" in transport
    assert 'parameters.get("filename*")' in transport
    assert "decodeRfc5987Value" in transport
    assert "percentDecodeUtf8" in transport
    assert "responseSpec.binaryDecoder().apply(bodyBytes)" in transport
    assert "request.responseFilename()" not in transport
    assert "public static final class PreviewForm" not in server_types
    assert "public record DemoPacket(" in server_types
    assert "public static DemoPacket parse(byte[] bytes)" in server_types
    assert "@RequestMapping(path = \"/api/media/preview\", method = {RequestMethod.POST})" in preview_annotation
    assert '@ApiBlueprintOperation("api.media.post.preview")' in preview_annotation
    assert '"api.media.get.download"' in spring_assertions
    assert '"com.example.generated.api.runtime.GenApiTypes.MediaUpload"' in spring_assertions
    assert '"com.example.generated.api.runtime.GenApiRawResponse"' in spring_assertions
    assert '"com.example.generated.api.runtime.GenApiStreamResponse"' in spring_assertions
    assert '"com.example.generated.api.types.api.media.GenMediaTypes.DemoPacket"' in spring_assertions
