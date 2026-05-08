from __future__ import annotations

import json
from pathlib import Path

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


def _write_inspect_blueprint(tmp_path: Path) -> None:
    pkg = tmp_path / "blueprints"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint, Error, Model, Toast
from api_blueprint.engine.model import String

class CommonErr(Model):
    UNKNOWN = Error(
        -1,
        "未知错误",
        toast=Toast(
            key="common.unknown",
            default="未知错误",
            level="error",
        ),
    )

class SubmitBody(Model):
    name = String(description="name")

class SubmitResult(Model):
    message = String(description="message")

bp = Blueprint(root="/api", errors=[CommonErr])
with bp.group("/demo") as views:
    views.POST("/submit").REQ(SubmitBody).RSP(SubmitResult)
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _write_inspect_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[targets]]
id = "go.server"
kind = "go-server"
out_dir = "golang/server"
module = "example.com/generated"

[[targets]]
id = "typescript.client"
kind = "typescript-client"
out_dir = "typescript"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return config_path


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
    assert manifest["capabilities"]["kotlin-client"]["routes"] == ["rpc", "legacy_ws", "stream", "channel"]
    assert manifest["capabilities"]["python-client"]["implemented"] is True


def test_api_gen_manifest_writes_agent_profile_and_shards(tmp_path):
    _write_blueprint(tmp_path)
    config_path = tmp_path / "api-blueprint.toml"
    out_path = tmp_path / "agent.json"
    shards_dir = tmp_path / "contract.d"
    config_path.write_text(
        """
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[targets]]
id = "contract"
kind = "contract"
out_dir = "."
formats = ["agent-json", "agent-markdown", "shards"]

[[targets]]
id = "typescript.client"
kind = "typescript-client"
out_dir = "typescript"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        api_gen,
        [
            "manifest",
            "-c",
            str(config_path),
            "--profile",
            "agent",
            "--out",
            str(out_path),
            "--shards-dir",
            str(shards_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    agent = json.loads(out_path.read_text(encoding="utf-8"))
    assert agent["kind"] == "api-blueprint.agent"
    assert agent["version"] == "1.0"
    assert agent["generator"]["version"] == "1.0.0"
    assert agent["counts"]["routes"] == 1
    assert agent["routes"][0]["shard"] == "api-blueprint.contract.d/routes/api.demo.get.ping.json"
    assert "typescript.client" in agent["routes"][0]["artifacts"]
    assert (shards_dir / "index.json").is_file()
    route_shard = json.loads((shards_dir / "routes" / "api.demo.get.ping.json").read_text(encoding="utf-8"))
    assert route_shard["route"]["id"] == "api.demo.get.ping"
    assert route_shard["schemas"]


def test_api_gen_manifest_keeps_sibling_target_artifacts_portable(tmp_path):
    service_root = tmp_path / "services" / "agent"
    scripts_dir = service_root / "scripts"
    package_dir = scripts_dir / "blueprints"
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "app.py").write_text(
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
    (service_root / "go.mod").write_text("module example.com/agent\n\ngo 1.23\n", encoding="utf-8")
    config_path = scripts_dir / "api-blueprint.toml"
    out_path = scripts_dir / "agent.json"
    config_path.write_text(
        """
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[targets]]
id = "go.server"
kind = "go-server"
out_dir = "../internal/views"
module = "example.com/agent"

[[targets]]
id = "typescript.client"
kind = "typescript-client"
out_dir = "../../../webui/src/lib/api"

[[targets]]
id = "gui.v3"
kind = "wails-transport"
version = "v3"
server = "go.server"
clients = ["typescript.client"]
overlay_name = "wailsv3"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        api_gen,
        [
            "manifest",
            "-c",
            str(config_path),
            "--profile",
            "agent",
            "--out",
            str(out_path),
        ],
    )

    assert result.exit_code == 0, result.output
    agent = json.loads(out_path.read_text(encoding="utf-8"))
    artifacts = agent["routes"][0]["artifacts"]
    assert artifacts["go.server"]["files"] == [
        "../internal/views/routes/api/demo/gen_interface.go",
        "../internal/views/routes/api/demo/gen_protos.go",
    ]
    assert artifacts["go.server"]["imports"] == ["example.com/agent/internal/views/routes/api/demo"]
    assert artifacts["typescript.client"]["files"] == [
        "../../../webui/src/lib/api/api/routes/api/demo/client.ts",
        "../../../webui/src/lib/api/api/routes/api/demo/models.ts",
    ]
    assert artifacts["gui.v3"]["files"] == [
        "../internal/views/transports/wailsv3/api/demo/gen_service.go",
        "../../../webui/src/lib/api/api/transports/wailsv3/api/demo/client.ts",
    ]
    payload = json.dumps(agent)
    assert "/Volumes/" not in payload
    assert "example.com/agent/Volumes" not in payload


def test_api_gen_inspect_routes_route_and_files(tmp_path):
    _write_inspect_blueprint(tmp_path)
    config_path = _write_inspect_config(tmp_path)

    routes = CliRunner().invoke(api_gen, ["inspect", "routes", "-c", str(config_path)])
    assert routes.exit_code == 0, routes.output
    assert "routes: 1" in routes.output
    assert "- api.demo.post.submit POST /api/demo/submit (rpc)" in routes.output
    assert "targets: go.server, typescript.client" in routes.output

    route = CliRunner().invoke(api_gen, ["inspect", "route", "api.demo.post.submit", "-c", str(config_path)])
    assert route.exit_code == 0, route.output
    assert "request: SubmitBody" in route.output
    assert "response: SubmitResult" in route.output
    assert "[go.server]" in route.output
    assert "golang/server/routes/api/demo/gen_interface.go" in route.output

    files = CliRunner().invoke(
        api_gen,
        ["inspect", "files", "-c", str(config_path), "--route", "api.demo.post.submit", "--target", "typescript.client"],
    )
    assert files.exit_code == 0, files.output
    assert "[typescript.client]" in files.output
    assert "typescript/api/routes/api/demo/client.ts" in files.output
    assert "go.server" not in files.output


def test_api_gen_inspect_schema_errors_and_json(tmp_path):
    _write_inspect_blueprint(tmp_path)
    config_path = _write_inspect_config(tmp_path)

    schema = CliRunner().invoke(api_gen, ["inspect", "schema", "SubmitBody", "-c", str(config_path)])
    assert schema.exit_code == 0, schema.output
    assert "schema: SubmitBody" in schema.output
    assert "- name: string" in schema.output
    assert "inbound routes: api.demo.post.submit" in schema.output

    errors = CliRunner().invoke(api_gen, ["inspect", "errors", "-c", str(config_path), "--route", "api.demo.post.submit"])
    assert errors.exit_code == 0, errors.output
    assert "route: api.demo.post.submit" in errors.output
    assert "- CommonErr.UNKNOWN code=-1 message=未知错误" in errors.output
    assert "toast: key=common.unknown" in errors.output

    payload_result = CliRunner().invoke(
        api_gen,
        ["inspect", "files", "-c", str(config_path), "--route", "/api/demo/submit", "--json"],
    )
    assert payload_result.exit_code == 0, payload_result.output
    payload = json.loads(payload_result.output)
    assert payload["route"] == "api.demo.post.submit"
    assert "go.server" in payload["targets"]


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


def test_api_gen_module_does_not_expose_legacy_split_commands() -> None:
    for name in ("gen_golang", "gen_typescript", "gen_kotlin", "gen_grpc", "gen_wails"):
        assert not hasattr(apigen_module, name)


def test_api_gen_help_only_lists_unified_1_0_commands() -> None:
    result = CliRunner().invoke(api_gen, ["--help"])

    assert result.exit_code == 0
    assert "1.0" in result.output
    assert "vNext" not in result.output
    for command in ("generate", "list-targets", "explain-target", "manifest", "diff", "check", "inspect"):
        assert command in result.output
    for legacy in ("gen-golang", "gen-typescript", "gen-kotlin", "gen-grpc", "gen-wails"):
        assert legacy not in result.output
