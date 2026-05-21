from __future__ import annotations

from .helpers import *


def test_java_generates_typed_binary_writer_parser_and_schema_paths(tmp_path: Path) -> None:
    schema = parse_binary_schema(
        """
# packet DemoPacket

endian: little
content-type: application/octet-stream

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| item_count | u16 | 1 | max=1,sizeof=items | item count |

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| items | Item | item_count | | items |

## struct Item

| field | type | count | rule | comment |
|---|---|---:|---|---|
| id | u32 | 1 | min=1 | item id |
| label_len | u8 | 1 | sizeof=label,max=16 | label length |
| label | bytes | label_len | | label |
""".strip(),
        source_path="demo_packet.md",
    )
    bp = Blueprint(root="/api")
    with bp.group("/binary") as binary:
        binary.POST("/packet").REQ_BINARY(schema).RSP(Result)

    output_dir = tmp_path / "java"
    writer = JavaClientWriter(output_dir, package="com.example.generated")
    writer.register(bp)
    writer.gen()

    binary_text = (
        output_dir / "com/example/generated/api/routes/api/binary/GenBinaryTypes.java"
    ).read_text(encoding="utf-8")
    runtime_text = (output_dir / "com/example/generated/api/runtime/binary/GenBinaryRuntime.java").read_text(
        encoding="utf-8"
    )

    assert "public record DemoPacket(" in binary_text
    assert "public record DemoPacketHeader(" in binary_text
    assert "public record DemoPacketBody(" in binary_text
    assert "public record DemoPacketItem(" in binary_text
    assert '@JsonProperty("item_count") Integer itemCount' in binary_text
    assert '@JsonProperty("label_len") Integer labelLen' in binary_text
    assert "public static GenApiBinaryBody toBinaryBody(DemoPacket value)" in binary_text
    assert "public static DemoPacket parse(byte[] bytes)" in binary_text
    assert 'throw GenBinaryRuntime.wrapBinaryField("DemoPacket.body", error);' in binary_text
    assert 'throw GenBinaryRuntime.wrapBinaryIndex("items", index, error);' in binary_text
    assert 'GenBinaryRuntime.requireRange("id", value.id().longValue(), 1L, Long.MAX_VALUE);' in binary_text
    assert (
        'GenBinaryRuntime.requireSize("label_len.label", GenBinaryRuntime.binarySize(value.label()), value.labelLen().longValue());'
        in binary_text
    )
    assert 'reader.readU32("id")' in binary_text
    assert "class BinaryEncodeException" in runtime_text
    assert "class BinaryDecodeException" in runtime_text
    assert "String path()" in runtime_text
    assert "wrapBinaryField" in runtime_text
    assert "wrapBinaryIndex" in runtime_text
