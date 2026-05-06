from __future__ import annotations

import json

from click.testing import CliRunner

import api_blueprint.cli.apigen as apigen_module
from api_blueprint.cli.apigen import api_gen


def _write_blueprint(tmp_path):
    pkg = tmp_path / "blueprints"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint
from api_blueprint.engine.model import String

bp = Blueprint(root="/api")
with bp.group("/demo") as views:
    views.GET("/ping").RSP(message=String(description="message"))
""".strip()
        + "\n",
        encoding="utf-8",
    )


def test_api_gen_manifest_writes_contract_json(tmp_path):
    _write_blueprint(tmp_path)
    config_path = tmp_path / "api-blueprint.toml"
    out_path = tmp_path / "contract.json"
    config_path.write_text(
        """
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[targets]]
id = "contract"
kind = "contract"
out_dir = "."
formats = ["json"]

[[targets]]
id = "kotlin.client"
kind = "kotlin-client"
out_dir = "kotlin"
package = "com.example.generated"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(api_gen, ["manifest", "-c", str(config_path), "--out", str(out_path)])

    assert result.exit_code == 0, result.output
    manifest = json.loads(out_path.read_text(encoding="utf-8"))
    assert manifest["routes"][0]["id"] == "api.demo.get.ping"
    assert manifest["targets"] == [
        {
            "id": "contract",
            "kind": "contract",
            "out_dir": ".",
            "formats": ["json"],
        },
        {
            "id": "kotlin.client",
            "kind": "kotlin-client",
            "out_dir": "kotlin",
            "package": "com.example.generated",
        },
    ]
    assert manifest["capabilities"]["kotlin-client"]["implemented"] is True
    assert manifest["capabilities"]["kotlin-client"]["routes"] == ["rpc"]
    assert manifest["capabilities"]["python-client"]["implemented"] is False


def test_api_gen_diff_reports_breaking_changes(tmp_path):
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    before.write_text(json.dumps({"routes": [{"id": "api.demo.get.ping", "hash": "a"}], "schemas": {}}), encoding="utf-8")
    after.write_text(json.dumps({"routes": [], "schemas": {}}), encoding="utf-8")

    result = CliRunner().invoke(api_gen, ["diff", str(before), str(after)])

    assert result.exit_code == 1
    assert "BREAKING" in result.output
    assert "route removed: api.demo.get.ping" in result.output


def test_api_gen_check_fails_when_kotlin_target_selects_connection_route(tmp_path):
    _write_blueprint(tmp_path)
    (tmp_path / "blueprints" / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint
from api_blueprint.engine.model import String, Model

class Event(Model):
    value = String(description="value")

bp = Blueprint(root="/api")
with bp.group("/demo") as views:
    views.STREAM("/events").SERVER_MESSAGE(Event)
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[targets]]
id = "kotlin.client"
kind = "kotlin-client"
out_dir = "kotlin"
package = "com.example.generated"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(api_gen, ["check", "-c", str(config_path)])

    assert result.exit_code != 0
    assert "kotlin-client does not support stream route" in str(result.exception)


def test_api_gen_check_fails_for_reserved_target(tmp_path):
    _write_blueprint(tmp_path)
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[targets]]
id = "python.client"
kind = "python-client"
out_dir = "python"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(api_gen, ["check", "-c", str(config_path)])

    assert result.exit_code != 0
    assert "python-client is reserved but not implemented" in str(result.exception)


def test_api_gen_module_does_not_expose_legacy_split_commands() -> None:
    for name in ("gen_golang", "gen_typescript", "gen_kotlin", "gen_grpc", "gen_wails"):
        assert not hasattr(apigen_module, name)


def test_api_gen_help_only_lists_unified_vnext_commands() -> None:
    result = CliRunner().invoke(api_gen, ["--help"])

    assert result.exit_code == 0
    for command in ("generate", "list-targets", "explain-target", "manifest", "diff", "check"):
        assert command in result.output
    for legacy in ("gen-golang", "gen-typescript", "gen-kotlin", "gen-grpc", "gen-wails"):
        assert legacy not in result.output
