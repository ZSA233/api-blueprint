from __future__ import annotations

import enum

from .helpers import *
from api_blueprint.engine.model import Array, Enum, Int, OneOf, LegacyStringID


def _typescript_format_violations(output_dir: Path) -> list[str]:
    violations: list[str] = []
    for path in sorted(output_dir.rglob("*.ts")):
        relative_path = path.relative_to(output_dir).as_posix()
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), 1):
            if line.rstrip(" \t") != line:
                violations.append(f"{relative_path}:{line_number}: trailing whitespace")
        blank_run = _max_consecutive_blank_lines(text)
        if blank_run >= 3:
            violations.append(f"{relative_path}: {blank_run} consecutive blank lines")
    return violations


def _typescript_request_block_holes(text: str) -> list[str]:
    holes: list[str] = []
    request_block_start: int | None = None
    for line_number, line in enumerate(text.splitlines(), 1):
        if request_block_start is None:
            if line == "    request: {":
                request_block_start = line_number
            continue
        if line.startswith("    }"):
            request_block_start = None
            continue
        if not line.strip():
            holes.append(f"request block at line {request_block_start} has empty line {line_number}")
    return holes


def test_typescript_generation_allows_real_shared_group_without_alias_rewrite(tmp_path: Path):
    bp = Blueprint(root="/api")
    with bp.group("/shared") as views:
        views.GET("/ping").RSP(message=String(description="message"))

    output_dir = tmp_path / "typescript"
    output_dir.mkdir()
    writer = TypeScriptWriter(output_dir)
    writer.register(bp)
    writer.gen()

    assert (output_dir / "api" / "routes" / "api" / "shared" / "gen_client.ts").is_file()
    assert (output_dir / "api" / "runtime" / "gen_client.ts").is_file()

def test_typescript_root_routes_use_root_client_file_without_reserved_slug(tmp_path: Path):
    bp = Blueprint(root="/api")
    bp.GET("/status").RSP(message=String(description="message"))
    with bp.group("/root") as views:
        views.GET("/ping").RSP(message=String(description="message"))

    output_dir = tmp_path / "typescript"
    output_dir.mkdir()
    writer = TypeScriptWriter(output_dir)
    writer.register(bp)
    writer.gen()

    assert (output_dir / "api" / "routes" / "api" / "client.ts").is_file()
    assert (output_dir / "api" / "routes" / "api" / "root" / "client.ts").is_file()
    assert not (output_dir / "api" / "routes" / "_root").exists()
    assert not (output_dir / "api" / "transports" / "http" / "api" / "_root").exists()

def test_typescript_writer_blocks_legacy_group_cleanup_when_user_client_exists(tmp_path: Path):
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/ping").RSP(message=String(description="message"))

    output_dir = tmp_path / "typescript"
    output_dir.mkdir()
    legacy_client = output_dir / "api" / "demo" / "client.ts"
    legacy_client.parent.mkdir(parents=True)
    legacy_client.write_text("// user custom client shim\n", encoding="utf-8")

    writer = TypeScriptWriter(output_dir)
    writer.register(bp)

    with pytest.raises(ValueError, match="legacy generated layout contains user-owned or unknown files"):
        writer.gen()

    assert legacy_client.exists()

def test_typescript_writer_removes_safe_legacy_shared_dir(tmp_path: Path):
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/ping").RSP(message=String(description="message"))

    output_dir = tmp_path / "typescript"
    output_dir.mkdir()
    legacy_shared = output_dir / "api" / "shared"
    legacy_shared.mkdir(parents=True)
    (legacy_shared / "gen_client.ts").write_text("// generated\n", encoding="utf-8")
    (legacy_shared / "client.ts").write_text("export * from './gen_client';\n", encoding="utf-8")
    (legacy_shared / "gen_models.ts").write_text("// generated\n", encoding="utf-8")
    (legacy_shared / "models.ts").write_text("export * from './gen_models';\n", encoding="utf-8")
    (legacy_shared / "gen_index.ts").write_text("// generated\n", encoding="utf-8")
    (legacy_shared / "index.ts").write_text('export * from "./gen_index";\n', encoding="utf-8")

    writer = TypeScriptWriter(output_dir)
    writer.register(bp)
    writer.gen()

    assert not legacy_shared.exists()


def test_typescript_generated_output_format_invariants(tmp_path: Path) -> None:
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/ping").RSP(message=String(description="message"))
        views.GET("/search").ARGS(q=String(description="q")).RSP(message=String(description="message"))
        views.POST("/submit").REQ(Payload).RSP(message=String(description="message"))

    output_dir = tmp_path / "typescript"
    output_dir.mkdir()
    writer = TypeScriptWriter(output_dir)
    writer.register(bp)
    writer.gen()

    client_text = (output_dir / "api" / "routes" / "api" / "demo" / "gen_client.ts").read_text(encoding="utf-8")
    assert "request: {} = {}" in client_text
    assert "request: {\n      query?: Types.SearchQuery;\n    } = {}" in client_text
    assert _typescript_format_violations(output_dir) == []
    assert _typescript_request_block_holes(client_text) == []


def test_typescript_generated_enums_include_member_comments(tmp_path: Path) -> None:
    class ActionKind(enum.IntEnum):
        CREATE = 1  # Create item
        UPDATE = 2  # Update item

    class ActionPayload(Model):
        action = Enum[ActionKind](description="action")

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.POST("/action").REQ(ActionPayload).RSP(ActionPayload)

    output_dir = tmp_path / "typescript"
    output_dir.mkdir()
    writer = TypeScriptWriter(output_dir)
    writer.register(bp)
    writer.gen()

    types_text = (output_dir / "api" / "runtime" / "gen_types.ts").read_text(encoding="utf-8")
    assert "/** Create item */" in types_text
    assert "CREATE = 1" in types_text
    assert "/** Update item */" in types_text
    assert "UPDATE = 2" in types_text


def test_typescript_generates_legacy_json_compat_union_types(tmp_path: Path) -> None:
    class LegacyPayload(Model):
        target = OneOf(String(), Array[String](), description="target")
        ids = Array[OneOf(String(), Int())](description="ids")
        normalized = Array[LegacyStringID](description="normalized")
        room_id = LegacyStringID(alias="roomId", description="room id")

    bp = Blueprint(root="/api")
    with bp.group("/legacy") as views:
        views.GET("/payload").RSP(LegacyPayload)

    output_dir = tmp_path / "typescript"
    output_dir.mkdir()
    writer = TypeScriptWriter(output_dir)
    writer.register(bp)
    writer.gen()

    runtime_types = (output_dir / "api" / "runtime" / "gen_types.ts").read_text(encoding="utf-8")
    assert "target: string | Array<string>;" in runtime_types
    assert "ids: Array<string | number>;" in runtime_types
    assert "normalized: Array<string>;" in runtime_types
    assert "roomId: string;" in runtime_types


def test_typescript_http_narrow_transport_entrypoint_does_not_import_wails_factories(tmp_path: Path) -> None:
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/ping").RSP(message=String(description="message"))

    output_dir = tmp_path / "typescript"
    output_dir.mkdir()
    for writer in (
        TypeScriptWriter(output_dir, transport_kind="http"),
        TypeScriptWriter(output_dir, transport_kind="wails-v2", overlay_name="wailsv2"),
        TypeScriptWriter(output_dir, transport_kind="wails-v3", overlay_name="wailsv3"),
    ):
        writer.register(bp)
        writer.gen()

    http_factory_text = (output_dir / "api" / "transports" / "http" / "api" / "gen_factory.ts").read_text(
        encoding="utf-8"
    )
    http_index_text = (output_dir / "api" / "transports" / "http" / "gen_index.ts").read_text(encoding="utf-8")
    aggregate_text = (output_dir / "api" / "transports" / "gen_clients.ts").read_text(encoding="utf-8")

    assert "wails" not in http_factory_text.lower()
    assert "wails" not in http_index_text.lower()
    assert "createWailsV2Clients" in aggregate_text
    assert "createWailsV3Clients" in aggregate_text
