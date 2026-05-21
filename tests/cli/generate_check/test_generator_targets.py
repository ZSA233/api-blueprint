from __future__ import annotations

from click.testing import CliRunner

from api_blueprint.cli.apigen import api_gen
from api_blueprint.application import generator
from api_blueprint.config import Config, resolve_config


def test_vnext_targets_load_and_resolve_dependencies(tmp_path):
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[targets]]
id = "go.server"
kind = "go-server"
out_dir = "golang"
module = "example.com/project/golang"

[[targets]]
id = "typescript.client"
kind = "typescript-client"
out_dir = "typescript"
base_url = "http://localhost:2333"

[[targets]]
id = "flutter.client"
kind = "flutter-client"
out_dir = "flutter"
package = "api_blueprint_example"
base_url = "http://localhost:2333"

[[targets]]
id = "wails.v3"
kind = "wails-transport"
version = "v3"
server = "go.server"
clients = ["typescript.client"]
frontend_mode = "external"

[[targets]]
id = "grpc.proto"
kind = "grpc-proto"
out_dir = "grpc/protos"
package = "example.api"
go_package_prefix = "example.com/project/grpc/go"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = Config.load(config_path)
    assert [target.id for target in config.targets] == [
        "go.server",
        "typescript.client",
        "flutter.client",
        "wails.v3",
        "grpc.proto",
    ]

    resolved = resolve_config(config_path)
    assert resolved.targets[0].out_dir == (tmp_path / "golang").resolve()
    assert resolved.targets[2].package == "api_blueprint_example"
    assert resolved.targets[3].server == "go.server"
    assert resolved.targets[3].clients == ("typescript.client",)


def test_vnext_targets_reject_missing_dependency(tmp_path):
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[targets]]
id = "wails.v3"
kind = "wails-transport"
version = "v3"
server = "go.server"
clients = ["typescript.client"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(api_gen, ["list-targets", "-c", str(config_path)])

    assert result.exit_code != 0
    assert "unknown server target" in str(result.exception)


def test_api_gen_list_targets_outputs_vnext_targets(tmp_path):
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[targets]]
id = "contract"
kind = "contract"
out_dir = "."
formats = ["json", "markdown"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(api_gen, ["list-targets", "-c", str(config_path)])

    assert result.exit_code == 0
    assert result.output.strip() == f"contract\tcontract\t{tmp_path.resolve()}"


def test_generation_plan_includes_grpc_proto_dependency_for_stub_target(tmp_path):
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[targets]]
id = "grpc.proto"
kind = "grpc-proto"
out_dir = "grpc/protos"
package = "example.api"

[[targets]]
id = "grpc.python"
kind = "grpc-python"
proto = "grpc.proto"
out_dir = "grpc/python"
files = ["api/**/*.proto"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    resolved = resolve_config(config_path)

    planned = generator.generation_plan(resolved.targets, ("grpc.python",))

    assert [target.id for target in planned] == ["grpc.proto", "grpc.python"]


def test_generation_plan_does_not_add_proto_dependency_for_raw_proto_stub(tmp_path):
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[targets]]
id = "grpc.python"
kind = "grpc-python"
source_root = "protocols/grpc"
out_dir = "grpc/python"
files = ["**/*.proto"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    resolved = resolve_config(config_path)

    planned = generator.generation_plan(resolved.targets, ("grpc.python",))

    assert [target.id for target in planned] == ["grpc.python"]


def test_generation_plan_includes_python_http_transport_dependencies(tmp_path):
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[targets]]
id = "python.server"
kind = "python-server"
out_dir = "python/server"
python_package_root = "server_app"

[[targets]]
id = "python.client"
kind = "python-client"
out_dir = "python/client"
python_package_root = "client_app"

[[targets]]
id = "http"
kind = "http-transport"
server = "python.server"
clients = ["python.client"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    resolved = resolve_config(config_path)

    planned = generator.generation_plan(resolved.targets, ("http",))

    assert [target.id for target in planned] == ["python.server", "python.client", "http"]


def test_generation_plan_includes_java_http_transport_dependencies(tmp_path):
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
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
    resolved = resolve_config(config_path)

    planned = generator.generation_plan(resolved.targets, ("http.java",))

    assert [target.id for target in planned] == ["java.server", "java.client", "http.java"]


def test_generation_plan_includes_flutter_http_transport_dependencies(tmp_path):
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[targets]]
id = "go.server"
kind = "go-server"
out_dir = "golang/server"
module = "example.com/project/server"

[[flutter.client]]
id = "flutter.client"
out_dir = "flutter"
package = "api_blueprint_example"

[[transport.http]]
id = "http.flutter"
server = "go.server"
clients = ["flutter.client"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    resolved = resolve_config(config_path)

    planned = generator.generation_plan(resolved.targets, ("http.flutter",))

    assert [target.id for target in planned] == ["go.server", "flutter.client", "http.flutter"]
