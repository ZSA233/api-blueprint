from __future__ import annotations

from .helpers import *


def test_wails_codegen_name_filter_uses_resolved_operation_name_for_same_path_methods(tmp_path: Path):
    config = tmp_path / "api-blueprint.toml"
    shared_go = tmp_path / "golang"
    shared_ts = tmp_path / "typescript"
    for path in (shared_go, shared_ts):
        path.mkdir()

    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    _write_wails_vnext_config(
        config,
        go_out=shared_go.name,
        ts_out=shared_ts.name,
        include=("name:CurrentGet",),
    )
    _write_same_path_method_blueprint_package(tmp_path)

    result = _invoke_wails_generate(config)
    assert result.exit_code == 0, result.output

    go_service = (shared_go / "transports" / "wailsv3" / "api" / "settings" / "gen_service.go").read_text(
        encoding="utf-8"
    )
    ts_bindings = (shared_ts / "api" / "transports" / "wailsv3" / "gen_bindings.ts").read_text(encoding="utf-8")
    assert "CurrentGet" in go_service
    assert "CurrentPut" not in go_service
    assert "CurrentGet" in ts_bindings
    assert "CurrentPut" not in ts_bindings

def test_wails_codegen_uses_go_safe_route_package_segments(tmp_path: Path):
    config = tmp_path / "api-blueprint.toml"
    shared_go = tmp_path / "golang"
    shared_ts = tmp_path / "typescript"
    for path in (shared_go, shared_ts):
        path.mkdir()
    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    _write_wails_vnext_config(config, go_out=shared_go.name, ts_out=shared_ts.name)
    _write_go_safe_route_blueprint_package(tmp_path)

    result = _invoke_wails_generate(config)
    assert result.exit_code == 0, result.output

    assert (shared_go / "routes" / "api_v1" / "admin_v1" / "gen_interface.go").is_file()
    assert (shared_go / "transports" / "wailsv3" / "api_v1" / "admin_v1" / "gen_service.go").is_file()
    bindings = (shared_ts / "api-v1" / "transports" / "wailsv3" / "gen_bindings.ts").read_text(
        encoding="utf-8"
    )
    assert "example.com/generated/golang/transports/wailsv3/api_v1/admin_v1.AdminV1Service.Ping" in bindings

def test_wails_codegen_rejects_go_reserved_namespace_segments(tmp_path: Path):
    config = tmp_path / "api-blueprint.toml"
    shared_go = tmp_path / "golang"
    shared_ts = tmp_path / "typescript"
    for path in (shared_go, shared_ts):
        path.mkdir()

    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    _write_wails_vnext_config(config, go_out=shared_go.name, ts_out=shared_ts.name)
    pkg = tmp_path / "blueprints"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint

bp = Blueprint(root="/api")
with bp.group("/_demo") as views:
    views.GET("/ping").RSP()
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    result = _invoke_wails_generate(config)
    assert result.exit_code != 0
    assert "保留目录段[_demo]" in result.output
