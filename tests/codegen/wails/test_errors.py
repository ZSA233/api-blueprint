from __future__ import annotations

from .helpers import *


def test_wails_codegen_errors_when_filters_remove_all_routes(tmp_path: Path):
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
    _write_wails_vnext_config(config, go_out=shared_go.name, ts_out=shared_ts.name, include=("group:missing",))
    _write_blueprint_package(tmp_path)

    result = _invoke_wails_generate(config)
    assert result.exit_code != 0
    assert "没有可生成的 route" in result.output
