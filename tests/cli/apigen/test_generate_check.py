from __future__ import annotations

from .helpers import *


def test_api_gen_diff_reports_breaking_changes(tmp_path):
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    before.write_text(json.dumps({"routes": [{"id": "api.demo.get.ping", "hash": "a"}], "schemas": {}}), encoding="utf-8")
    after.write_text(json.dumps({"routes": [], "schemas": {}}), encoding="utf-8")

    result = CliRunner().invoke(api_gen, ["diff", str(before), str(after)])

    assert result.exit_code == 1
    assert "BREAKING" in result.output
    assert "route removed: api.demo.get.ping" in result.output

def test_api_gen_check_allows_kotlin_target_to_select_connection_route(tmp_path):
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

    assert result.exit_code == 0, result.output

def test_api_gen_check_accepts_python_client_target(tmp_path):
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
    python_package_root = "generated"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(api_gen, ["check", "-c", str(config_path)])

    assert result.exit_code == 0, result.output

def test_api_gen_check_accepts_java_targets(tmp_path):
    _write_blueprint(tmp_path)
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[java.server]]
id = "java.server"
out_dir = "java/server"
module = "com.example.generated"

[[java.client]]
id = "java.client"
out_dir = "java/client"
module = "com.example.generated"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(api_gen, ["check", "-c", str(config_path)])

    assert result.exit_code == 0, result.output

def test_api_gen_generate_reports_success(tmp_path):
    _write_blueprint(tmp_path)
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[contract]]
id = "contract"
out_dir = "."
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(api_gen, ["generate", "-c", str(config_path), "--target", "contract"])

    assert result.exit_code == 0, result.output
    assert "ok: generated 1 target(s)" in result.output

def test_api_gen_check_and_generate_fail_for_duplicate_explicit_operation_names(tmp_path):
    _write_duplicate_operation_blueprint(tmp_path)
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[contract]]
id = "contract"
out_dir = "."
""".strip()
        + "\n",
        encoding="utf-8",
    )

    check_result = CliRunner().invoke(api_gen, ["check", "-c", str(config_path)])
    assert check_result.exit_code == 1
    assert "duplicate operation name" in check_result.output
    assert "TaskEvents" in check_result.output
    assert "operation_id" in check_result.output

    generate_result = CliRunner().invoke(api_gen, ["generate", "-c", str(config_path), "--target", "contract"])
    assert generate_result.exit_code == 1
    assert "duplicate operation name" in generate_result.output
    assert "TaskEvents" in generate_result.output
