from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Callable

import pytest

from api_blueprint.engine import Blueprint
from api_blueprint.engine.binary_schema import parse_binary_schema
from api_blueprint.engine.model import Model, String
from api_blueprint.writer.golang.client import GolangClientWriter
from api_blueprint.writer.golang.server.writer import GolangWriter
from api_blueprint.writer.java import JavaClientWriter, JavaServerWriter
from api_blueprint.writer.kotlin import KotlinWriter
from api_blueprint.writer.python import PythonClientWriter
from api_blueprint.writer.typescript.writer import TypeScriptWriter


class BinaryResult(Model):
    status = String(description="status")


def _binary_schema(packet_name: str, const_value: int):
    return parse_binary_schema(
        f"""
# packet {packet_name}

endian: little

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| kind | Kind | 1 | const={const_value} | packet kind |
| flags | Flags | 1 | min=0 | flags |
| item_count | u16 | 1 | max=4,sizeof=items | item count |

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| items | Item | item_count | | items |

## struct Item

| field | type | count | rule | comment |
|---|---|---:|---|---|
| id | u16 | 1 | min=1 | id |

## enum Kind : u16

| name | value | comment |
|---|---:|---|
| Primary | 1 | primary |
| Secondary | 2 | secondary |

## bitflags Flags : u32

| name | bits | rule | comment |
|---|---:|---|---|
| HasItems | 0 | | has items |
| Mode | 1..2 | enum=Kind | mode |
| Reserved | 3..31 | const=0 | reserved |
""".strip(),
        source_path=f"{packet_name}.md",
    )


def _multi_binary_blueprint() -> Blueprint:
    bp = Blueprint(root="/api")
    with bp.group("/binary") as views:
        views.POST("/packet").REQ_BINARY(_binary_schema("DemoPacket", 1)).RSP(BinaryResult)
        views.POST("/audit-packet").REQ_BINARY(_binary_schema("AuditPacket", 2)).RSP(BinaryResult)
    return bp


def _colliding_packet_name_blueprint() -> Blueprint:
    bp = Blueprint(root="/api")
    with bp.group("/binary") as views:
        views.POST("/packet").REQ_BINARY(_binary_schema("DemoPacket", 1)).RSP(BinaryResult)
        views.POST("/packet-alt").REQ_BINARY(_binary_schema("Demo_Packet", 1)).RSP(BinaryResult)
    return bp


@pytest.mark.toolchain_smoke
def test_go_client_scopes_binary_schema_internal_symbols(tmp_path: Path) -> None:
    output_dir = tmp_path / "client"
    output_dir.mkdir()
    (output_dir / "go.mod").write_text("module example.com/generated/client\n\ngo 1.23.8\n", encoding="utf-8")

    writer = GolangClientWriter(output_dir, module="example.com/generated/client")
    writer.register(_multi_binary_blueprint())
    writer.gen()

    schema_text = (output_dir / "routes/api/binary/gen_binary.go").read_text(encoding="utf-8")
    assert "type binaryState struct" not in schema_text
    assert "type demoPacketBinaryState struct" in schema_text
    assert "type auditPacketBinaryState struct" in schema_text
    assert "type DemoPacketItem struct" in schema_text
    assert "type AuditPacketItem struct" in schema_text
    assert "type DemoPacketKind uint16" in schema_text
    assert "type AuditPacketKind uint16" in schema_text
    assert "func WriteDemoPacketItem(" in schema_text
    assert "func WriteAuditPacketItem(" in schema_text

    if shutil.which("go") is None:
        pytest.skip("go toolchain is not available")
    subprocess.run(["go", "test", "./..."], cwd=output_dir, check=True)


@pytest.mark.toolchain_smoke
def test_go_server_scopes_binary_schema_internal_symbols(tmp_path: Path) -> None:
    output_dir = tmp_path / "server"
    output_dir.mkdir()
    (output_dir / "go.mod").write_text("module example.com/generated/server\n\ngo 1.23.8\n", encoding="utf-8")

    writer = GolangWriter(output_dir)
    writer.register(_multi_binary_blueprint())
    writer.gen()

    schema_text = (output_dir / "routes/api/binary/_gen_binary/gen_binary.go").read_text(encoding="utf-8")
    assert "type _binaryState struct" not in schema_text
    assert "type demoPacketBinaryState struct" in schema_text
    assert "type auditPacketBinaryState struct" in schema_text
    assert "type DemoPacketItem struct" in schema_text
    assert "type AuditPacketItem struct" in schema_text
    assert "type DemoPacketKind uint16" in schema_text
    assert "type AuditPacketKind uint16" in schema_text
    assert "func readDemoPacketItem(" in schema_text
    assert "func readAuditPacketItem(" in schema_text

    if shutil.which("go") is None:
        pytest.skip("go toolchain is not available")
    subprocess.run(["go", "test", "./routes/api/binary/_gen_binary"], cwd=output_dir, check=True)


@pytest.mark.toolchain_smoke
def test_typescript_scopes_binary_schema_internal_symbols(tmp_path: Path) -> None:
    output_dir = tmp_path / "typescript"
    writer = TypeScriptWriter(output_dir)
    writer.register(_multi_binary_blueprint())
    writer.gen()

    schema_text = (output_dir / "api/routes/api/binary/gen_binary.ts").read_text(encoding="utf-8")
    assert "interface BinaryState" not in schema_text
    assert "interface DemoPacketBinaryState" in schema_text
    assert "interface AuditPacketBinaryState" in schema_text
    assert "export interface DemoPacketItem" in schema_text
    assert "export interface AuditPacketItem" in schema_text
    assert "export type DemoPacketKind = number;" in schema_text
    assert "export type AuditPacketKind = number;" in schema_text
    assert "function newDemoPacketBinaryState()" in schema_text
    assert "function newAuditPacketBinaryState()" in schema_text
    assert "export function writeDemoPacketItem(" in schema_text
    assert "export function writeAuditPacketItem(" in schema_text

    if shutil.which("tsc") is None:
        pytest.skip("TypeScript compiler is not available")
    subprocess.run(
        [
            "tsc",
            "--noEmit",
            "--target",
            "ES2022",
            "--module",
            "esnext",
            "--moduleResolution",
            "bundler",
            "api/routes/api/binary/gen_binary.ts",
        ],
        cwd=output_dir,
        check=True,
    )


def test_python_scopes_binary_schema_internal_symbols(tmp_path: Path) -> None:
    output_dir = tmp_path / "python"
    writer = PythonClientWriter(output_dir)
    writer.register(_multi_binary_blueprint())
    writer.gen()

    schema_text = (
        output_dir / "api_blueprint_generated/api/routes/api/binary/gen_binary.py"
    ).read_text(encoding="utf-8")
    assert "class DemoPacketItem:" in schema_text
    assert "class AuditPacketItem:" in schema_text
    assert "class DemoPacketKind:" in schema_text
    assert "class AuditPacketKind:" in schema_text
    assert "def write_demopacket_item(" in schema_text
    assert "def write_auditpacket_item(" in schema_text
    assert "def write_item(" not in schema_text
    compile(schema_text, "gen_binary.py", "exec")


def test_kotlin_scopes_binary_schema_internal_symbols(tmp_path: Path) -> None:
    output_dir = tmp_path / "kotlin"
    writer = KotlinWriter(output_dir, package="com.example.generated")
    writer.register(_multi_binary_blueprint())
    writer.gen()

    schema_text = (
        output_dir / "com/example/generated/api/routes/api/binary/GenBinaryTypes.kt"
    ).read_text(encoding="utf-8")
    assert "public class DemoPacketBinaryState" in schema_text
    assert "public class AuditPacketBinaryState" in schema_text
    assert "public data class DemoPacketItem(" in schema_text
    assert "public data class AuditPacketItem(" in schema_text
    assert "public object DemoPacketKindValues" in schema_text
    assert "public object AuditPacketKindValues" in schema_text
    assert "public fun writeDemoPacketItem(" in schema_text
    assert "public fun writeAuditPacketItem(" in schema_text


@pytest.mark.parametrize(
    ("label", "writer_factory"),
    [
        ("go client", lambda output: GolangClientWriter(output, module="example.com/generated/client")),
        ("go server", lambda output: GolangWriter(output)),
        ("typescript", lambda output: TypeScriptWriter(output)),
        ("python", lambda output: PythonClientWriter(output)),
        ("kotlin", lambda output: KotlinWriter(output, package="com.example.generated")),
        ("java client", lambda output: JavaClientWriter(output, package="com.example.generated")),
        ("java server", lambda output: JavaServerWriter(output, package="com.example.generated", spring_public_paths=["/api/**"])),
    ],
)
def test_binary_schema_normalized_packet_name_collisions_fail(
    tmp_path: Path,
    label: str,
    writer_factory: Callable[[Path], object],
) -> None:
    output_dir = tmp_path / label.replace(" ", "-")
    output_dir.mkdir()
    if label.startswith("go "):
        (output_dir / "go.mod").write_text("module example.com/generated\n\ngo 1.23.8\n", encoding="utf-8")

    writer = writer_factory(output_dir)
    writer.register(_colliding_packet_name_blueprint())

    with pytest.raises(ValueError, match="duplicate binary schema generated name"):
        writer.gen()
