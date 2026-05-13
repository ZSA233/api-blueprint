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
