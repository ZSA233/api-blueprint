from __future__ import annotations

from .helpers import *


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
