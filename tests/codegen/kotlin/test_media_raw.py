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
        views.GET("/download").RSP_FILE(content_type="application/octet-stream", filename="sample-é.txt")
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
    server_runtime = (server_dir / package_root / "runtime/GenApiServerResponse.kt").read_text(encoding="utf-8")
    ktor = (server_dir / package_root / "transports/ktor/api/media/GenMediaKtorRoutes.kt").read_text(
        encoding="utf-8"
    )

    assert "public data class ApiFilePart(" in runtime
    assert "public val path: String? = null" in runtime
    assert "public fun openStream(): InputStream" in runtime
    assert "public fun fromPath(" in runtime
    assert "public data class ApiRawResponse(" in runtime
    assert "public class ApiStreamResponse(" in runtime
    assert "body: InputStream" in runtime
    assert "public constructor(" in runtime
    assert "body: ByteArray," in runtime
    assert "public fun readChunk(maxBytes: Int = API_STREAM_CHUNK_SIZE): ByteArray?" in runtime
    assert "public fun readAllBytes(): ByteArray" in runtime
    assert "public val responseKind: String = \"json\"" in runtime
    assert "public val stream: ApiStreamResponse? = null" in runtime
    assert "stream ?: ApiStreamResponse(" in runtime
    assert "public class ApiStreamResponse(" in server_runtime
    assert "public data class ApiServerConfig(" in server_runtime
    assert "body: InputStream" in server_runtime
    assert "public fun readAllBytes(): ByteArray" in server_runtime
    assert 'name.equals("filename*", ignoreCase = true)' in runtime
    assert "decodeContentDispositionFilenameStar" in runtime
    assert "percentDecode(value.substring(secondQuote + 1), charset)" in runtime
    assert "public val multipart: Any? = null" in runtime
    assert "public val responseDecoder: ((ApiResponse) -> T)? = null" in runtime
    assert "public class BinaryReader" in binary_runtime
    assert "public fun parse(bytes: ByteArray): DemoPacket" in route_types
    assert "public val image: ApiFilePart" in runtime_types
    assert "multipartSerializer = MediaUpload.serializer()" in route_client
    assert 'responseDecoder = { response -> response.toRawResponse("image/jpeg") }' in route_client
    assert 'responseDecoder = { response -> response.toRawResponse("application/octet-stream") }' in route_client
    assert 'response.toRawResponse("application/octet-stream", "sample-é.txt")' not in route_client
    assert 'responseKind = "byte_stream"' in route_client
    assert 'responseDecoder = { response -> response.toStreamResponse("multipart/x-mixed-replace") }' in route_client
    assert "responseDecoder = { response -> DemoPacketWire.parse(response.body) }" in route_client
    assert "MultipartBody.Builder().setType(MultipartBody.FORM)" in transport
    assert "File(file.path).asRequestBody(mediaType)" in transport
    assert "file.bytes.toRequestBody(mediaType)" in transport
    assert 'if (request.responseKind == "byte_stream")' in transport
    assert "body = body.byteStream()" in transport
    assert "isJsonContentType(contentType)" in transport
    assert "decodeEnvelopeApiErrorPayload(responseText, request.routeId, request.responseEnvelope)" in runtime
    assert "body = response.body?.bytes() ?: ByteArray(0)" in transport
    assert "response.body?.string().orEmpty().toByteArray(Charsets.UTF_8)" in transport
    stream_response_helper = transport.split("private fun streamResponse", 1)[1].split("@Suppress", 1)[0]
    assert "body.byteStream()" in stream_response_helper
    assert "decodeMultipart(call, MediaUpload.serializer(), config)" in ktor
    assert "receiveFilePart(part, config)" in ktor
    assert 'put("path", JsonPrimitive(path))' in ktor
    assert "JsonArray(bytes.map { JsonPrimitive(it.toInt()) })" not in ktor
    assert "respondPayloadTooLarge(call)" in ktor
    assert "JsonPrimitive(it.toInt() and 0xFF)" not in ktor
    assert "private data class HttpRouteInfo(" in ktor
    assert 'defaultFilename = "sample-é.txt"' in ktor
    assert "respondRaw(call, result, HTTP_ROUTE_API_MEDIA_POST_PREVIEW.response)" in ktor
    assert "respondRaw(call, result, HTTP_ROUTE_API_MEDIA_GET_DOWNLOAD.response)" in ktor
    assert "respondRaw(call, result, HTTP_ROUTE_API_MEDIA_GET_MJPEG.response)" in ktor
    assert "respondOutputStream(contentType = contentType(response.contentType))" in ktor
    assert "val read = stream.body.read(buffer)" in ktor
    assert "contentDispositionAttachment(effectiveFilename)" in ktor
    assert "filename*=UTF-8''${percentEncodeUtf8(filename)}" in ktor
    assert '"%%%02X".format(code)' in ktor
    assert "DemoPacketWire.toBinaryBody(result).toByteArray()" in ktor
