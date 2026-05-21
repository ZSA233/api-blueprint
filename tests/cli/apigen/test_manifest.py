from __future__ import annotations

from .helpers import *


def test_api_gen_manifest_defaults_to_index_profile(tmp_path):
    _write_blueprint(tmp_path)
    config_path = tmp_path / "api-blueprint.toml"
    out_path = tmp_path / "index.json"
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
    index = json.loads(out_path.read_text(encoding="utf-8"))
    assert index["kind"] == "api-blueprint.index"
    assert index["routes"][0]["id"] == "api.demo.get.ping"
    assert "schemas" not in index
    assert "errors" not in index
    assert "connections" not in index
    assert "schemas" not in index["routes"][0]
    assert "errors" not in index["routes"][0]
    assert "targets" not in index["routes"][0]
    assert "artifacts" not in index["routes"][0]
    assert index["queries"] == {
        "routes": "api-gen inspect routes -c api-blueprint.toml",
        "route": "api-gen inspect route <route-id> [<route-id> ...] -c api-blueprint.toml",
        "schema": "api-gen inspect schema <SchemaName> [<SchemaName> ...] -c api-blueprint.toml",
        "errors": "api-gen inspect errors --route <route-id> [--route <route-id> ...] -c api-blueprint.toml",
        "files": "api-gen inspect files --route <route-id> [--route <route-id> ...] --target <target-id> -c api-blueprint.toml",
        "full_contract": "api-gen manifest --profile full --out api-blueprint.contract.json -c api-blueprint.toml",
    }
    assert index["targets"][0] == {
        "id": "contract",
        "kind": "contract",
        "out_dir": ".",
        "role": "contract",
        "route_count": 1,
    }
    assert index["targets"][1]["id"] == "kotlin.client"
    assert index["targets"][1]["kind"] == "kotlin-client"
    assert "package" not in index["targets"][1]
    assert "capabilities" not in index

def test_api_gen_manifest_writes_full_contract_profile(tmp_path):
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

    result = CliRunner().invoke(
        api_gen,
        ["manifest", "-c", str(config_path), "--profile", "full", "--out", str(out_path)],
    )

    assert result.exit_code == 0, result.output
    manifest = json.loads(out_path.read_text(encoding="utf-8"))
    assert manifest["routes"][0]["id"] == "api.demo.get.ping"
    assert manifest["capabilities"]["kotlin-client"]["implemented"] is True
    assert manifest["capabilities"]["kotlin-client"]["routes"] == ["rpc", "stream", "channel"]
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
    assert agent["version"] == "2.0"
    assert agent["generator"]["version"] == __version__
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
        "../internal/views/routes/api/demo/gen_types.go",
    ]
    assert artifacts["go.server"]["imports"] == ["example.com/agent/internal/views/routes/api/demo"]
    assert artifacts["typescript.client"]["files"] == [
        "../../../webui/src/lib/api/api/routes/api/demo/client.ts",
        "../../../webui/src/lib/api/api/routes/api/demo/types.ts",
    ]
    assert artifacts["gui.v3"]["files"] == [
        "../internal/views/transports/wailsv3/api/demo/gen_service.go",
        "../../../webui/src/lib/api/api/transports/wailsv3/api/demo/client.ts",
    ]
    payload = json.dumps(agent)
    assert "/Volumes/" not in payload
    assert "example.com/agent/Volumes" not in payload
