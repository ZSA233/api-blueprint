from __future__ import annotations

from .helpers import *


def test_swift_writer_generates_field_level_binary_schema_codec(tmp_path: Path) -> None:
    schema = parse_binary_schema(
        """
# packet DemoPacket

endian: little
content-type: application/octet-stream

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
    with bp.group("/binary") as views:
        views.POST("/packet").REQ_BINARY(schema).RSP(payload=String(description="payload"))
        views.GET("/packet").RSP_BINARY_SCHEMA(schema)

    writer = SwiftWriter(tmp_path / "swift", package="ApiBlueprintExampleClient", module="ABClient")
    writer.register(bp)
    writer.gen()

    route_dir = tmp_path / "swift" / "Sources" / "ABClientAPIRoutes" / "API" / "Routes" / "API" / "Binary"
    runtime_binary = (
        tmp_path / "swift" / "Sources" / "ABClientRuntime" / "Binary" / "GenBinaryRuntime.swift"
    ).read_text(encoding="utf-8")
    route_client = (route_dir / "GenBinaryAPI.swift").read_text(encoding="utf-8")
    binary_text = (route_dir / "GenBinary.swift").read_text(encoding="utf-8")

    assert "public final class APIBinaryWriter" in runtime_binary
    assert "public final class APIBinaryReader" in runtime_binary
    assert "public struct APIBinaryEncodeError" in runtime_binary
    assert "public struct APIBinaryDecodeError" in runtime_binary
    assert "public func writeU24(_ path: String, _ value: Int) throws" in runtime_binary
    assert "public func readU24(_ path: String) throws -> Int" in runtime_binary
    assert (
        "public func apiBinaryWrapIndex(_ path: String, _ index: Int, _ error: APIBinaryDecodeError)"
        in runtime_binary
    )

    assert "public enum DemoPacketFlagsValues" in binary_text
    assert "public static let hasPayload: Int = 1" in binary_text
    assert "public struct DemoPacketHeader: Codable, Sendable" in binary_text
    assert "public struct DemoPacketBody: Codable, Sendable" in binary_text
    assert "public struct DemoPacketItem: Codable, Sendable" in binary_text
    assert "public var data: Data" not in binary_text
    assert "public var payload: Data" in binary_text
    assert "public var items: [DemoPacketItem]" in binary_text
    assert "try writer.writeBytesExact(\"magic\", Data([65, 66, 80, 49]), 4)" in binary_text
    assert "try apiBinaryRequireDecode(\"flags\", (Int(flags) & 4294967294) == 0" in binary_text
    assert "try apiBinaryRequireSize(\"items\", apiBinarySize(value.items), itemsCount)" in binary_text
    assert "let itemsCount = state.itemCount" in binary_text
    assert "try DemoPacketWire.writeDemoPacketItem(item, writer: writer, state: state, path: \"\")" in binary_text
    assert "let payloadCount = state.payloadLen" in binary_text
    assert "let payload = try reader.readBytes(\"payload\", payloadCount)" in binary_text
    assert "try apiBinaryRequire(\"checksum\", Int(value.checksum) == state.itemCount + state.payloadLen" in binary_text
    assert "public static func encode(_ value: DemoPacket) throws -> Data" in binary_text
    assert "public static func decode(_ data: Data) throws -> DemoPacket" in binary_text
    assert "public func encodeDemoPacket(_ value: DemoPacket) throws -> Data" in binary_text
    assert "public func decodeDemoPacket(_ data: Data) throws -> DemoPacket" in binary_text

    assert "binary: DemoPacket? = nil" in route_client
    assert "let binaryBody = try binary?.encode()" in route_client
    assert "decodeData: { data, _, _ in try decodeDemoPacket(data) }" in route_client
