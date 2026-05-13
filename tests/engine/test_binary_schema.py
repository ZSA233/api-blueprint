from __future__ import annotations

import pytest

from api_blueprint.engine import Blueprint, Model
from api_blueprint.engine.binary_schema import BinarySchemaError, parse_binary_schema
from api_blueprint.engine.model import String


VALID_SCHEMA = """
# packet DemoPacket

endian: little
content-type: application/octet-stream
content-encoding: identity,gzip

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| magic | bytes | 4 | const="DEMO" | magic |
| item_num | u32 | 1 | min=1,max=8,sizeof=items | item count |

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| items | DemoItem | item_num | | items |

## struct DemoItem

| field | type | count | rule | comment |
|---|---|---:|---|---|
| payload_len | u32 | 1 | max=1024,sizeof=payload | byte count |
| payload | bytes | payload_len | | raw payload |
""".strip()


def test_markdown_binary_schema_parses_strict_heading_tables_and_renders_html() -> None:
    schema = parse_binary_schema(VALID_SCHEMA, source_path="demo_packet.md")

    assert schema.name == "DemoPacket"
    assert schema.endian == "little"
    assert schema.content_encoding == ("identity", "gzip")
    assert schema.sections[0].name == "DemoPacketHeader"
    assert schema.sections[1].fields[0].type == "DemoItem"
    assert schema.structs["DemoItem"].fields[1].count == "payload_len"
    assert "<table>" in schema.rendered_html


def test_markdown_binary_schema_rejects_dynamic_count_without_bound() -> None:
    bad_schema = VALID_SCHEMA.replace("max=1024,sizeof=payload", "sizeof=payload")

    with pytest.raises(BinarySchemaError, match="dynamic count\\[payload_len\\] must have max"):
        parse_binary_schema(bad_schema, source_path="bad_packet.md")


def test_markdown_binary_schema_rejects_bad_table_columns() -> None:
    bad_schema = VALID_SCHEMA.replace("| field | type | count | rule | comment |", "| name | type | count | rule | comment |", 1)

    with pytest.raises(BinarySchemaError, match="table columns must be"):
        parse_binary_schema(bad_schema, source_path="bad_columns.md")


def test_markdown_binary_schema_supports_value_sets_padding_and_24_bit_fields() -> None:
    schema = parse_binary_schema(
        """
# packet RichPacket

endian: little

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| kind | RichKind | 1 | const=1 | enum |
| flags | RichFlags | 1 | max=7 | flags |
| pad0 | padding | 1 | | hidden |
| reserved0 | reserved | 2 | | hidden |
| short_code | u24 | 1 | min=1,max=16777215 | code |
| signed_delta | i24 | 1 | min=-8388608,max=8388607 | delta |

## enum RichKind : u16

| name | value | comment |
|---|---:|---|
| Metric | 1 | metric |
| Debug | 2 | debug |

## bitflags RichFlags : u32

| name | bits | rule | comment |
|---|---:|---|---|
| HasPayload | 0 | | payload |
| HasScores | 1 | | scores |
| Mode | 2..3 | enum=RichKind | mode |
| Reserved | 4..31 | const=0 | reserved |

## bitflags SingleBitFlags : u8

| name | bit | comment |
|---|---:|---|
| Enabled | 0 | enabled |
""".strip(),
        source_path="rich_packet.md",
    )

    fields = schema.sections[0].fields
    assert schema.enums["RichKind"].base_type == "u16"
    assert schema.bitflags["RichFlags"].values[1].name == "HasScores"
    assert schema.bitflags["RichFlags"].values[1].value == "2"
    assert schema.bitflags["RichFlags"].values[2].bit_start == 2
    assert schema.bitflags["RichFlags"].values[2].bit_end == 3
    assert schema.bitflags["RichFlags"].values[2].rule["enum"] == "RichKind"
    assert schema.bitflags["RichFlags"].reserved_zero_mask == 4294967280
    assert schema.bitflags["SingleBitFlags"].values[0].bit == "0"
    assert fields[2].type == "padding"
    assert fields[4].type == "u24"
    assert fields[5].rule["min"] == "-8388608"


def test_markdown_binary_schema_rejects_dynamic_padding_and_bad_value_sets() -> None:
    dynamic_padding = VALID_SCHEMA.replace(
        "| magic | bytes | 4 | const=\"DEMO\" | magic |",
        "| pad | padding | item_num | | bad |",
    )
    with pytest.raises(BinarySchemaError, match="padding count must be a fixed byte length"):
        parse_binary_schema(dynamic_padding, source_path="dynamic_padding.md")

    bad_value_set = VALID_SCHEMA + "\n\n## enum Bad : f64\n\n| name | value | comment |\n|---|---:|---|\n| A | 1 | a |\n"
    with pytest.raises(BinarySchemaError, match="base type must be an integer field type"):
        parse_binary_schema(bad_value_set, source_path="bad_value_set.md")

    overlapping_flags = VALID_SCHEMA + """

## bitflags BadFlags : u8

| name | bits | rule | comment |
|---|---:|---|---|
| A | 0..2 | | a |
| B | 2..3 | | b |
"""
    with pytest.raises(BinarySchemaError, match="overlapping bitflags bits"):
        parse_binary_schema(overlapping_flags, source_path="bad_flags.md")

    bad_flags_rule = VALID_SCHEMA + """

## bitflags BadFlags : u8

| name | bits | rule | comment |
|---|---:|---|---|
| Reserved | 1..7 | const=1 | bad |
"""
    with pytest.raises(BinarySchemaError, match="only supports const=0"):
        parse_binary_schema(bad_flags_rule, source_path="bad_flags_rule.md")


def test_req_binary_replaces_removed_req_bin_api() -> None:
    class LegacyBinary(Model):
        checksum = String(description="checksum")

    bp = Blueprint(root="/api")
    route = bp.POST("/upload")
    with pytest.raises(ValueError, match="REQ_BIN\\(Model\\) is removed"):
        route.REQ_BIN(LegacyBinary)

    route.REQ_BINARY(parse_binary_schema(VALID_SCHEMA, source_path="demo_packet.md"))
    with pytest.raises(ValueError, match="cannot be combined with REQ_BINARY"):
        route.REQ(json=String(description="json"))
