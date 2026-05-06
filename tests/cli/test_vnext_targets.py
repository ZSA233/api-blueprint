from __future__ import annotations

from click.testing import CliRunner

from api_blueprint.cli.apigen import api_gen
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
        "wails.v3",
        "grpc.proto",
    ]

    resolved = resolve_config(config_path)
    assert resolved.targets[0].out_dir == (tmp_path / "golang").resolve()
    assert resolved.targets[2].server == "go.server"
    assert resolved.targets[2].clients == ("typescript.client",)


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
