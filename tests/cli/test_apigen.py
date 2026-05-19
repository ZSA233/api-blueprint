from __future__ import annotations

import json
from pathlib import Path

from api_blueprint import __version__
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


def _write_go_safe_inspect_blueprint(tmp_path: Path) -> None:
    pkg = tmp_path / "blueprints"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint
from api_blueprint.engine.model import String

bp = Blueprint(root="/api-v1")
with bp.group("/admin/v1") as views:
    views.GET("/ping").RSP(message=String(description="message"))
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _write_go_safe_inspect_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[targets]]
id = "go.server"
kind = "go-server"
out_dir = "golang/server"
module = "example.com/generated/server"

[[targets]]
id = "go.client"
kind = "go-client"
out_dir = "golang/client"
module = "example.com/generated/client"

[[targets]]
id = "typescript.client"
kind = "typescript-client"
out_dir = "typescript"

[[targets]]
id = "desktop.v3"
kind = "wails-transport"
version = "v3"
server = "go.server"
clients = ["typescript.client"]
overlay_name = "wailsv3"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return config_path


def _write_binary_inspect_blueprint(tmp_path: Path) -> None:
    pkg = tmp_path / "blueprints"
    binary_dir = pkg / "binary"
    binary_dir.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (binary_dir / "demo_packet.md").write_text(
        """
# packet DemoPacket

endian: little
content-type: application/octet-stream
content-encoding: identity,gzip

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| magic | bytes | 4 | const="DEMO" | magic |
| item_num | u32 | 1 | min=1,max=8,sizeof=items | item count |

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| items | DemoItem | item_num | | items |

## struct DemoItem

| field | type | count | rule | comment |
|---|---|---:|---|---|
| value | u32 | 1 | max=100 | value |
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (pkg / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint, provider
from api_blueprint.engine.model import String

bp = Blueprint(root="/api", providers=[provider.Req(), provider.Handle(), provider.Rsp()])
with bp.group("/demo") as views:
    views.POST("/binary").ARGS(token=String(description="token")).REQ_BINARY("./binary/demo_packet.md").RSP(ok=String(description="ok"))
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _write_bulk_inspect_blueprint(tmp_path: Path) -> None:
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

class PingResult(Model):
    message = String(description="message")

bp = Blueprint(root="/api", errors=[CommonErr])
with bp.group("/demo") as views:
    views.POST("/submit").REQ(SubmitBody).RSP(SubmitResult)
    views.GET("/ping").RSP(PingResult)
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _write_connection_inspect_blueprint(tmp_path: Path) -> None:
    pkg = tmp_path / "blueprints"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint, ConnectionDelivery, ConnectionScope, Model
from api_blueprint.engine.model import String

class Open(Model):
    device_id = String(description="device id")

class ClientMessage(Model):
    text = String(description="text")

class ServerMessage(Model):
    text = String(description="text")

class Close(Model):
    reason = String(description="reason")

bp = Blueprint(root="/api")
with bp.group("/demo") as views:
    views.CHANNEL("/ws", scope=ConnectionScope.SESSION, delivery=ConnectionDelivery.UNORDERED, operation_id="Realtime").OPEN(Open).CLIENT_MESSAGE(ClientMessage).SERVER_MESSAGE(ServerMessage).CLOSE(Close)
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _write_duplicate_operation_blueprint(tmp_path: Path) -> None:
    pkg = tmp_path / "blueprints"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint
from api_blueprint.engine.model import String

bp = Blueprint(root="/api")
with bp.group("/demo") as views:
    views.GET("/events", operation_id="TaskEvents").RSP(message=String(description="message"))
    views.PUT("/events", operation_id="TaskEvents").RSP(message=String(description="message"))
""".strip()
        + "\n",
        encoding="utf-8",
    )


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


def test_api_gen_inspect_files_uses_go_safe_route_package_segments(tmp_path):
    _write_go_safe_inspect_blueprint(tmp_path)
    config_path = _write_go_safe_inspect_config(tmp_path)
    route_id = "api_v1.admin_v1.get.ping"

    go_server = CliRunner().invoke(
        api_gen,
        ["inspect", "files", "-c", str(config_path), "--route", route_id, "--target", "go.server"],
    )
    assert go_server.exit_code == 0, go_server.output
    assert "golang/server/routes/api_v1/admin_v1/gen_interface.go" in go_server.output
    assert "example.com/generated/server/golang/server/routes/api_v1/admin_v1" in go_server.output
    assert "routes/api-v1/admin/v1" not in go_server.output

    go_client = CliRunner().invoke(
        api_gen,
        ["inspect", "files", "-c", str(config_path), "--route", route_id, "--target", "go.client"],
    )
    assert go_client.exit_code == 0, go_client.output
    assert "golang/client/routes/api_v1/admin_v1/gen_client.go" in go_client.output
    assert "example.com/generated/client/golang/client/routes/api_v1/admin_v1" in go_client.output
    assert "routes/api-v1/admin/v1" not in go_client.output

    wails = CliRunner().invoke(
        api_gen,
        ["inspect", "files", "-c", str(config_path), "--route", route_id, "--target", "desktop.v3"],
    )
    assert wails.exit_code == 0, wails.output
    assert "golang/server/transports/wailsv3/api_v1/admin_v1/gen_service.go" in wails.output
    assert "transports/wailsv3/api-v1/admin/v1" not in wails.output


def test_api_gen_inspect_files_reports_java_artifacts(tmp_path):
    _write_inspect_blueprint(tmp_path)
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

    client_files = CliRunner().invoke(
        api_gen,
        ["inspect", "files", "-c", str(config_path), "--route", "api.demo.post.submit", "--target", "java.client"],
    )
    assert client_files.exit_code == 0, client_files.output
    assert "[java.client]" in client_files.output
    assert "java/client/com/example/generated/api/routes/api/demo/GenDemoApi.java" in client_files.output
    assert "java/client/com/example/generated/api/transports/http/GenJdkHttpApiTransport.java" in client_files.output

    server_files = CliRunner().invoke(
        api_gen,
        ["inspect", "files", "-c", str(config_path), "--route", "api.demo.post.submit", "--target", "java.server"],
    )
    assert server_files.exit_code == 0, server_files.output
    assert "[java.server]" in server_files.output
    assert "java/server/com/example/generated/api/routes/api/demo/GenDemoService.java" in server_files.output
    assert "java/server/com/example/generated/api/transports/http/api/demo/GenDemoController.java" in server_files.output


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


def test_api_gen_inspect_binary_schema(tmp_path):
    _write_binary_inspect_blueprint(tmp_path)
    config_path = _write_inspect_config(tmp_path)

    route = CliRunner().invoke(api_gen, ["inspect", "route", "api.demo.post.binary", "-c", str(config_path)])
    assert route.exit_code == 0, route.output
    assert "binary schema: DemoPacket" in route.output

    schema = CliRunner().invoke(api_gen, ["inspect", "binary-schema", "DemoPacket", "-c", str(config_path)])
    assert schema.exit_code == 0, schema.output
    assert "binary schema: DemoPacket" in schema.output
    assert "route: api.demo.post.binary" in schema.output
    assert "content-encoding: identity, gzip" in schema.output
    assert "- DemoPacketHeader fields=2" in schema.output
    assert "- DemoItem fields=1" in schema.output

    go_files = CliRunner().invoke(
        api_gen,
        ["inspect", "files", "-c", str(config_path), "--route", "api.demo.post.binary", "--target", "go.server"],
    )
    assert go_files.exit_code == 0, go_files.output
    assert "golang/server/routes/api/demo/_gen_binary/gen_binary.go" in go_files.output

    ts_files = CliRunner().invoke(
        api_gen,
        ["inspect", "files", "-c", str(config_path), "--route", "api.demo.post.binary", "--target", "typescript.client"],
    )
    assert ts_files.exit_code == 0, ts_files.output
    assert "typescript/api/routes/api/demo/gen_binary.ts" in ts_files.output


def test_api_gen_inspect_route_json_omits_shard_metadata(tmp_path):
    _write_bulk_inspect_blueprint(tmp_path)
    config_path = _write_inspect_config(tmp_path)

    single = CliRunner().invoke(
        api_gen,
        ["inspect", "route", "api.demo.post.submit", "-c", str(config_path), "--json"],
    )
    assert single.exit_code == 0, single.output
    single_payload = json.loads(single.output)
    assert single_payload["id"] == "api.demo.post.submit"
    assert "shard" not in single_payload

    bulk = CliRunner().invoke(
        api_gen,
        [
            "inspect",
            "route",
            "api.demo.post.submit",
            "api.demo.get.ping",
            "-c",
            str(config_path),
            "--json",
        ],
    )
    assert bulk.exit_code == 0, bulk.output
    bulk_payload = json.loads(bulk.output)
    assert bulk_payload["count"] == 2
    assert all("shard" not in route for route in bulk_payload["routes"])


def test_api_gen_inspect_supports_bulk_route_schema_files_and_errors(tmp_path):
    _write_bulk_inspect_blueprint(tmp_path)
    config_path = _write_inspect_config(tmp_path)

    routes = CliRunner().invoke(
        api_gen,
        [
            "inspect",
            "route",
            "api.demo.post.submit",
            "api.demo.get.ping",
            "-c",
            str(config_path),
            "--json",
        ],
    )
    assert routes.exit_code == 0, routes.output
    routes_payload = json.loads(routes.output)
    assert routes_payload["count"] == 2
    assert [route["id"] for route in routes_payload["routes"]] == [
        "api.demo.post.submit",
        "api.demo.get.ping",
    ]

    schemas = CliRunner().invoke(
        api_gen,
        ["inspect", "schema", "SubmitBody", "PingResult", "-c", str(config_path), "--json"],
    )
    assert schemas.exit_code == 0, schemas.output
    schemas_payload = json.loads(schemas.output)
    assert schemas_payload["count"] == 2
    assert [schema["name"] for schema in schemas_payload["schemas"]] == ["SubmitBody", "PingResult"]

    files = CliRunner().invoke(
        api_gen,
        [
            "inspect",
            "files",
            "-c",
            str(config_path),
            "--route",
            "api.demo.post.submit",
            "--route",
            "api.demo.get.ping",
            "--target",
            "typescript.client",
            "--json",
        ],
    )
    assert files.exit_code == 0, files.output
    files_payload = json.loads(files.output)
    assert files_payload["count"] == 2
    assert [route["route"] for route in files_payload["routes"]] == [
        "api.demo.post.submit",
        "api.demo.get.ping",
    ]
    assert set(files_payload["routes"][0]["targets"]) == {"typescript.client"}

    errors = CliRunner().invoke(
        api_gen,
        [
            "inspect",
            "errors",
            "-c",
            str(config_path),
            "--route",
            "api.demo.post.submit",
            "--route",
            "api.demo.get.ping",
            "--json",
        ],
    )
    assert errors.exit_code == 0, errors.output
    errors_payload = json.loads(errors.output)
    assert errors_payload["count"] == 2
    assert [route["route"] for route in errors_payload["routes"]] == [
        "api.demo.post.submit",
        "api.demo.get.ping",
    ]
    assert [route["count"] for route in errors_payload["routes"]] == [1, 1]


def test_api_gen_explain_target_shows_effective_mainline_target_summary(tmp_path):
    _write_blueprint(tmp_path)
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[contract]]
id = "contract"
out_dir = "."

[[go.server]]
id = "go.server"
out_dir = "golang/server"
module = "example.com/project/server"

[[typescript.client]]
id = "typescript.client"
out_dir = "typescript"

[[java.client]]
id = "java.client"
out_dir = "java/client"
module = "com.example.generated"
base_url = "http://localhost:2333"
include = ["tag:api"]
exclude = ["path:/api/demo/ws"]

[[transport.wails]]
id = "gui.v3"
version = "v3"
server = "go.server"
clients = ["typescript.client"]
include = ["path:/api/**"]
exclude = ["path:/api/demo/ping"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    contract = CliRunner().invoke(api_gen, ["explain-target", "-c", str(config_path), "--target", "contract"])
    assert contract.exit_code == 0, contract.output
    assert "id: contract" in contract.output
    assert "kind: contract" in contract.output
    assert "formats: [index]" in contract.output

    wails = CliRunner().invoke(api_gen, ["explain-target", "-c", str(config_path), "--target", "gui.v3"])
    assert wails.exit_code == 0, wails.output
    assert "kind: wails-transport" in wails.output
    assert "version: v3" in wails.output
    assert "overlay_name: wailsv3" in wails.output
    assert "frontend_mode: external" in wails.output
    assert "server: go.server" in wails.output
    assert "clients: [typescript.client]" in wails.output
    assert "include: [path:/api/**]" in wails.output
    assert "exclude: [path:/api/demo/ping]" in wails.output

    java_client = CliRunner().invoke(
        api_gen,
        ["explain-target", "-c", str(config_path), "--target", "java.client"],
    )
    assert java_client.exit_code == 0, java_client.output
    assert "kind: java-client" in java_client.output
    assert "package: com.example.generated" in java_client.output
    assert "base_url: http://localhost:2333" in java_client.output
    assert "include: [tag:api]" in java_client.output
    assert "exclude: [path:/api/demo/ws]" in java_client.output


def test_api_gen_inspect_route_uses_operation_id_for_channel_operation(tmp_path):
    _write_connection_inspect_blueprint(tmp_path)
    config_path = _write_inspect_config(tmp_path)

    result = CliRunner().invoke(
        api_gen,
        ["inspect", "route", "api.demo.channel.ws", "-c", str(config_path), "--json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["id"] == "api.demo.channel.ws"
    assert payload["operation"] == "Realtime"
    assert payload["connection"]["delivery"] == "unordered"


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

[[transport.http]]
id = "http.java"
server = "java.server"
clients = ["java.client"]
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
