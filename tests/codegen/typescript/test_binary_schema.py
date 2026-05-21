from __future__ import annotations

from .helpers import *


def test_typescript_client_generates_binary_overloads_runtime_and_transport(tmp_path: Path):
    schema = parse_binary_schema(
        """
# packet DemoPacket

endian: little

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| flags | Flags | 1 | min=0 | flags |
| pad0 | padding | 1 | | pad |
| code | u24 | 1 | min=1,max=16777215 | code |
| delta | i24 | 1 | min=-8,max=8 | delta |
| payload_len | u16 | 1 | max=16,sizeof=payload | payload length |

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| payload | bytes | payload_len | | payload |

## bitflags Flags : u32

| name | bits | rule | comment |
|---|---:|---|---|
| HasPayload | 0 | | payload |
| Reserved | 1..31 | const=0 | reserved |
""".strip(),
        source_path="demo_packet.md",
    )
    bp = Blueprint(root="/api", response_envelope=CodeMessageDataEnvelope)
    with bp.group("/binary") as views:
        views.POST("/packet").REQ_BINARY(schema).RSP(message=String(description="message"))

    output_dir = tmp_path / "typescript"
    output_dir.mkdir()
    writer = TypeScriptWriter(output_dir)
    writer.register(bp)
    writer.gen()

    route_text = (output_dir / "api" / "routes" / "api" / "binary" / "gen_client.ts").read_text(
        encoding="utf-8"
    )
    schema_text = (
        output_dir / "api" / "routes" / "api" / "binary" / "gen_binary.ts"
    ).read_text(encoding="utf-8")
    index_text = (output_dir / "api" / "routes" / "api" / "binary" / "gen_index.ts").read_text(
        encoding="utf-8"
    )
    runtime_text = (output_dir / "api" / "runtime" / "binary" / "gen_runtime.ts").read_text(encoding="utf-8")
    transport_text = (output_dir / "api" / "transports" / "http" / "gen_transport.ts").read_text(encoding="utf-8")

    assert "binary: Types.DemoPacket;" in route_text
    assert "binary: ApiBinaryBody;" in route_text
    assert "binary: Types.DemoPacket | ApiBinaryBody;" in route_text
    assert "DemoPacketWire.toBinaryBody(request.binary)" in route_text
    assert 'export * as Wire from "./wire";' not in index_text
    assert 'export * from "./types";' in index_text
    assert not (output_dir / "api" / "routes" / "api" / "binary" / "wire.ts").exists()
    assert "export const DemoPacketFlagsValues" in schema_text
    assert "HasPayload: 1" in schema_text
    assert "reserved bits must be zero" in schema_text
    assert "writer.writeU24" in schema_text
    assert "writer.writeI24" in schema_text
    assert "writer.writeZeroes" in schema_text
    assert _max_consecutive_blank_lines(schema_text) <= 1
    assert "class RawBinaryBody" in runtime_text
    assert "private writeScratch" in runtime_text
    assert "this.writeScratch(8);" in runtime_text
    assert "binaryBodyToUint8Array" in transport_text

def test_typescript_client_generates_binary_schema_response_decoder(tmp_path: Path):
    schema = parse_binary_schema(
        """
# packet AuditPacket

endian: little
content-type: application/vnd.audit-packet

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| kind | u8 | 1 | const=2 | kind |
| item_count | u16 | 1 | min=1,max=4,sizeof=items | item count |

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| items | AuditItem | item_count | | items |

## struct AuditItem

| field | type | count | rule | comment |
|---|---|---:|---|---|
| id | u32 | 1 | min=1 | item id |
        """.strip(),
        source_path="audit_packet.md",
    )
    bp = Blueprint(root="/api")
    with bp.group("/binary") as views:
        views.GET("/audit").RSP_BINARY_SCHEMA(schema)

    output_dir = tmp_path / "typescript"
    writer = TypeScriptWriter(output_dir)
    writer.register(bp)
    writer.gen()

    route_text = (output_dir / "api" / "routes" / "api" / "binary" / "gen_client.ts").read_text(
        encoding="utf-8"
    )
    binary_text = (output_dir / "api" / "routes" / "api" / "binary" / "gen_binary.ts").read_text(
        encoding="utf-8"
    )
    transport_text = (output_dir / "api" / "transports" / "http" / "gen_transport.ts").read_text(encoding="utf-8")

    assert "): Promise<Types.AuditPacket>" in route_text
    assert "const payload = await this.request<ArrayBuffer>({" in route_text
    assert 'responseType: "binary_schema"' in route_text
    assert "return AuditPacketWire.fromBytes(payload)" in route_text
    assert "{\n\n    const payload" not in route_text
    assert "({\n\n      routeId" not in route_text
    assert "    });\n\n    return AuditPacketWire" not in route_text
    assert "function parseAuditPacket(" in binary_text
    assert 'if (responseType === "binary_schema")' in transport_text
    assert "return await response.arrayBuffer() as unknown as R" in transport_text

def test_typescript_binary_schema_uses_local_diagnostic_paths_for_nested_writers(tmp_path: Path):
    schema = parse_binary_schema(
        """
# packet Inventory

endian: little

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| item_count | u8 | 1 | max=4 | item count |
| items | Item | item_count | | items |
| primary | Item | 1 | | primary item |

## struct Item

| field | type | count | rule | comment |
|---|---|---:|---|---|
| id | u16 | 1 | min=1 | item id |
""".strip(),
        source_path="inventory_packet.md",
    )
    bp = Blueprint(root="/api", response_envelope=CodeMessageDataEnvelope)
    with bp.group("/binary") as views:
        views.POST("/inventory").REQ_BINARY(schema).RSP(message=String(description="message"))

    output_dir = tmp_path / "typescript"
    output_dir.mkdir()
    writer = TypeScriptWriter(output_dir)
    writer.register(bp)
    writer.gen()

    schema_text = (
        output_dir / "api" / "routes" / "api" / "binary" / "gen_binary.ts"
    ).read_text(encoding="utf-8")
    runtime_text = (output_dir / "api" / "runtime" / "binary" / "gen_runtime.ts").read_text(encoding="utf-8")

    assert "readonly detail: string" in runtime_text
    assert "export function joinBinaryPath(" in runtime_text
    assert "export function indexBinaryPath(" in runtime_text
    assert "export function wrapBinaryField(" in runtime_text
    assert "export function wrapBinaryIndex(" in runtime_text
    assert "wrapBinaryPath(indexBinaryPath(path, index), write)" not in runtime_text
    assert 'throw wrapBinaryField("primary", error);' in schema_text
    assert 'throw wrapBinaryIndex("items", index, error);' in schema_text
    assert 'writeInventoryItem(item, writer, state, "");' in schema_text
    assert "=> wrapBinaryIndex(" not in schema_text
    assert 'requireRange("id", value.id, 1, Number.MAX_SAFE_INTEGER);' in schema_text
    assert 'writer.writeU16("id", value.id);' in schema_text
    assert '"Item.id"' not in schema_text
    assert "`[${index}]`" not in schema_text
