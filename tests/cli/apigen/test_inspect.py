from __future__ import annotations

from .helpers import *


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
    assert "java/server/com/example/generated/api/annotations/api/demo/GenSubmit.java" in server_files.output
    assert "java/server/com/example/generated/api/types/api/demo/GenDemoTypes.java" in server_files.output
    assert "java/server/com/example/generated/api/adapters/api/demo/GenDemoAdapters.java" in server_files.output
    assert "java/server/com/example/generated/api/spring/GenSpringMvcContractAssertions.java" in server_files.output

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

[[swift.client]]
id = "swift.client"
out_dir = "swift"
package = "ApiBlueprintExampleClient"
module = "ABClient"
base_url = "http://localhost:2333"
runtime_profile = "ios14-compat"
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

    swift_client = CliRunner().invoke(
        api_gen,
        ["explain-target", "-c", str(config_path), "--target", "swift.client"],
    )
    assert swift_client.exit_code == 0, swift_client.output
    assert "kind: swift-client" in swift_client.output
    assert "package: ApiBlueprintExampleClient" in swift_client.output
    assert "module: ABClient" in swift_client.output
    assert "base_url: http://localhost:2333" in swift_client.output
    assert "runtime_profile: ios14-compat" in swift_client.output
    assert "include: [tag:api]" in swift_client.output
    assert "exclude: [path:/api/demo/ws]" in swift_client.output

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
