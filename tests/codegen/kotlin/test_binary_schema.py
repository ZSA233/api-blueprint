from __future__ import annotations

from .helpers import *


def test_kotlin_writer_generates_binary_schema_client_and_writer(tmp_path):
    schema = parse_binary_schema(
        """
# packet DemoPacket

endian: little
content-type: application/octet-stream
content-encoding: identity,gzip

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| magic | bytes | 4 | const="ABP1" | magic |
| version | u16 | 1 | const=1 | protocol version |
| flags | Flags | 1 | min=0 | flags |
| item_count | u16 | 1 | min=1,max=8,sizeof=items | item count |
| payload_len | u32 | 1 | min=0,max=64,sizeof=payload | payload bytes |

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| items | Item | item_count | | items |
| payload | bytes | payload_len | encoding=utf-8 | payload |
| checksum | u32 | 1 | assert=item_count + payload_len | checksum |

## struct Item

| field | type | count | rule | comment |
|---|---|---:|---|---|
| id | u32 | 1 | min=1,max=999 | item id |
| enabled | bool | 1 | | enabled |
| score | f64 | 1 | | score |
| label_len | u8 | 1 | min=1,max=16,sizeof=label | label bytes |
| label | bytes | label_len | encoding=utf-8 | label |

## bitflags Flags : u32

| name | bits | rule | comment |
|---|---:|---|---|
| HasPayload | 0 | | payload |
| Reserved | 1..31 | const=0 | reserved |
""",
        source_path="demo_packet.md",
    )

    bp = Blueprint(root="/api")
    views = bp.group("/binary")
    views.POST("/packet", response_envelope=CodeMessageDataEnvelope).ARGS(
        trace=String(description="trace"),
    ).REQ_BINARY(schema).RSP(
        payload=String(description="payload"),
    )
    bp.is_built = True

    writer = KotlinWriter(tmp_path / "kotlin", package="com.example.generated")
    writer.register(bp)
    writer.gen()

    root_dir = tmp_path / "kotlin" / "com" / "example" / "generated" / "api"
    runtime_binary_text = (root_dir / "runtime" / "binary" / "GenBinaryRuntime.kt").read_text(encoding="utf-8")
    route_text = (root_dir / "routes" / "api" / "binary" / "GenBinaryApi.kt").read_text(encoding="utf-8")
    binary_text = (root_dir / "routes" / "api" / "binary" / "GenBinaryTypes.kt").read_text(encoding="utf-8")
    runtime_models_text = (root_dir / "runtime" / "GenApiTypes.kt").read_text(encoding="utf-8")
    http_text = (root_dir / "transports" / "http" / "GenOkHttpApiTransport.kt").read_text(encoding="utf-8")

    assert "public interface ApiBinaryBody" in runtime_binary_text
    assert "public data class EncodedBinaryBlock(" in runtime_binary_text
    assert "public class BinaryWriter" in runtime_binary_text
    assert "public fun writeBlock(path: String, block: EncodedBinaryBlock)" in runtime_binary_text
    assert "public val detail: String = message" in runtime_binary_text
    assert "public fun joinBinaryPath(path: String, field: String): String" in runtime_binary_text
    assert "public fun indexBinaryPath(path: String, index: Int): String" in runtime_binary_text
    assert "public fun wrapBinaryField(path: String, error: BinaryEncodeException): BinaryEncodeException" in runtime_binary_text
    assert "public fun wrapBinaryIndex(path: String, index: Int, error: BinaryEncodeException): BinaryEncodeException" in runtime_binary_text
    assert "public object GenBinary {" not in binary_text
    assert "public data class DemoPacket(" in binary_text
    assert "public object DemoPacketFlagsValues" in binary_text
    assert "reserved bits must be zero" in binary_text
    assert "public object DemoPacketWire" in binary_text
    assert "public fun writeDemoPacketItem(" in binary_text
    assert "public fun writeDemoPacketItemHeaderPayloadBlock(" not in binary_text
    assert "public fun writeDemoPacketBodyPayloadBlock(" in binary_text
    assert "public fun writeDemoPacketBodyItemsFragment(" in binary_text
    assert "public fun writeDemoPacketItem(" in binary_text
    assert "label: ByteString," in binary_text
    assert "\"Item.id\"" not in binary_text
    assert "writer.writeU32(\"id\", value.id)" in binary_text
    assert "writer.writeByteString(\"label\", label)" in binary_text
    assert "requireSize(\"label_len.label\", binarySize(value.label), value.labelLen.toLong())" in binary_text
    assert "writer.writeF64(\"score\", value.score)" in binary_text
    assert "try {\n\n" not in binary_text
    assert "reader.readBytes(\"magic\", 4L)\n\n            requireBinary" not in binary_text
    assert "requireBinary(\"magic\", value.magic.contentEquals(byteArrayOf(65, 66, 80, 49)), \"const mismatch\")\n\n            writer.writeBytesExact" not in binary_text
    assert "wrapBinaryIndex(\"items\", index, error)" in binary_text
    assert "wrapBinaryField(path, error)" in binary_text
    assert "+ \"[$index]\"" not in binary_text
    assert "public open suspend fun packet(" in route_text
    assert "binary: DemoPacket," in route_text
    assert "binary = DemoPacketWire.toBinaryBody(binary)" in route_text
    assert route_text.count("public open suspend fun packet(") == 2
    assert "binary: ApiBinaryBody," in route_text
    assert "binarySerializer" not in route_text
    assert "return transport.request(" in route_text
    assert "responseEnvelope = ApiResponseEnvelope(name = \"CodeMessageDataEnvelope\", kind = \"code_message_data\"" in route_text
    assert "val envelope = transport.request(" not in route_text
    assert "public data class GeneralResponse<T>(" not in runtime_models_text
    assert "override fun writeTo(sink: BufferedSink)" in http_text
    assert "binary.writeTo(sink)" in http_text


def test_kotlin_server_decodes_binary_schema_content_encoding(tmp_path):
    schema = parse_binary_schema(
        """
# packet DemoPacket

endian: little
content-type: application/octet-stream
content-encoding: identity,gzip,br

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| magic | bytes | 4 | const="ABP1" | magic |
""".strip(),
        source_path="demo_packet.md",
    )

    bp = Blueprint(root="/api")
    with bp.group("/binary") as views:
        views.POST("/packet").REQ_BINARY(schema).RSP(payload=String(description="payload"))
    with bp.group("/plain") as views:
        views.GET("/ping").RSP(payload=String(description="payload"))

    writer = KotlinServerWriter(tmp_path / "kotlin", package="com.example.generated")
    writer.register(bp)
    writer.gen()

    root_dir = tmp_path / "kotlin" / "com" / "example" / "generated" / "api"
    runtime_text = (root_dir / "runtime" / "GenApiServerResponse.kt").read_text(encoding="utf-8")
    ktor_text = (root_dir / "transports" / "ktor" / "api" / "binary" / "GenBinaryKtorRoutes.kt").read_text(
        encoding="utf-8"
    )
    plain_ktor_text = (root_dir / "transports" / "ktor" / "api" / "plain" / "GenPlainKtorRoutes.kt").read_text(
        encoding="utf-8"
    )

    assert "public typealias ApiBinaryContentDecoder = (ByteArray) -> ByteArray" in runtime_text
    assert "public val decompressedBinaryBodyMaxBytes: Long = 16L * 1024L * 1024L" in runtime_text
    assert "public val binaryContentDecoders: Map<String, ApiBinaryContentDecoder> = emptyMap()" in runtime_text
    assert "private data class HttpRouteInfo(" in ktor_text
    assert 'binaryContentEncodings = setOf("identity", "gzip", "br")' in ktor_text
    assert "DemoPacketWire.parse(receiveBinarySchemaBytes(call, config, HTTP_ROUTE_API_BINARY_POST_PACKET.request))" in ktor_text
    assert "io.ktor.utils.io.readAvailable\n\nimport java.io.ByteArrayInputStream" not in ktor_text
    assert "io.ktor.utils.io.readAvailable\n\nimport java.nio.file.Files" not in plain_ktor_text
    assert "GZIPInputStream(ByteArrayInputStream(encoded))" in ktor_text
    assert "config.binaryContentDecoders[encoding]" in ktor_text
    assert "respondUnsupportedContentEncoding(call)" in ktor_text
    assert "HttpStatusCode.UnsupportedMediaType" in ktor_text
