from __future__ import annotations

from .helpers import *


def test_flutter_writer_generates_binary_schema_codecs(tmp_path: Path) -> None:
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
| version | u16 | 1 | const=1 | version |
| item_count | u16 | 1 | min=1,max=8,sizeof=items | item count |

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| items | Item | item_count | | items |

## struct Item

| field | type | count | rule | comment |
|---|---|---:|---|---|
| id | u32 | 1 | max=100 | id |
""".strip()
    )

    bp = Blueprint(root="/api")
    with bp.group("/binary") as views:
        views.POST("/packet").REQ_BINARY(schema).RSP(ok=String(description="ok"))

    writer = FlutterWriter(tmp_path / "flutter", package="api_blueprint_example")
    writer.register(bp)
    writer.gen()

    route_dir = tmp_path / "flutter" / "lib" / "src" / "api" / "routes" / "api" / "binary"
    runtime_dir = tmp_path / "flutter" / "lib" / "src" / "api" / "runtime"
    binary_text = (route_dir / "gen_binary.dart").read_text(encoding="utf-8")
    runtime_text = (runtime_dir / "binary" / "gen_binary_runtime.dart").read_text(encoding="utf-8")
    route_text = (route_dir / "gen_binary_api.dart").read_text(encoding="utf-8")

    assert "class DemoPacket" in binary_text
    assert "class DemoPacketItem" in binary_text
    assert "Uint8List encodeDemoPacket(DemoPacket value)" in binary_text
    assert "DemoPacket decodeDemoPacket(Uint8List bytes)" in binary_text
    assert ") {\n\n    final" not in binary_text
    assert "reader.readBytes(apiBinaryJoinPath(path, \"magic\"), 4);\n\n      apiBinaryRequireCondition" not in binary_text
    assert "writer.writeU16(apiBinaryJoinPath(path, \"version\"), _version);\n\n    state" not in binary_text
    assert "class ApiBinaryWriter" in runtime_text
    assert "binary: encodeDemoPacket(packet)" in route_text
