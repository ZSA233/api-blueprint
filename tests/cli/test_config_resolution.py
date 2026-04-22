from __future__ import annotations

from api_blueprint.application.generation import list_grpc_jobs
from api_blueprint.config import Config, resolve_config
from tests.support import EXAMPLE_CONFIG


def test_example_config_loads_expected_values():
    config = Config.load(EXAMPLE_CONFIG)

    assert config.blueprint.entrypoints == ["blueprints.app:*"]
    assert config.blueprint.docs_server == "0.0.0.0:2332"
    assert config.golang.codegen_output == "golang"
    assert config.typescript is not None
    assert config.typescript.codegen_output == "typescript"
    assert config.typescript.base_url == "http://localhost:2333"
    assert config.grpc is not None
    assert [job.name for job in config.grpc.jobs] == ["python.greeter", "go.greeter"]


def test_resolve_config_converts_relative_outputs_to_absolute_paths():
    resolved = resolve_config(EXAMPLE_CONFIG)
    assert resolved.golang.output is not None
    assert resolved.golang.output.is_absolute()
    assert resolved.typescript is not None
    assert resolved.typescript.output is not None
    assert resolved.typescript.output.is_absolute()
    assert resolved.grpc is not None
    assert resolved.grpc.proto_root == (EXAMPLE_CONFIG.parent / "grpc" / "protos").resolve()
    assert resolved.grpc.jobs[0].output == (EXAMPLE_CONFIG.parent / "grpc" / "python").resolve()
    assert resolved.grpc.jobs[1].output == (EXAMPLE_CONFIG.parent / "grpc" / "go").resolve()


def test_grpc_only_config_loads_and_resolves_absolute_paths(tmp_path):
    proto_root = tmp_path / "protos"
    proto_root.mkdir()

    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[grpc]
proto_root = "protos"
include_paths = ["includes"]

[[grpc.jobs]]
name = "python.greeter"
preset = "python"
output = "generated/python"
protos = ["**/*.proto"]
include_paths = ["job-includes"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = Config.load(config_path)
    assert config.blueprint is None
    assert config.golang is None
    assert config.typescript is None
    assert config.grpc is not None
    assert config.grpc.jobs[0].name == "python.greeter"

    resolved = resolve_config(config_path)
    assert resolved.golang is None
    assert resolved.typescript is None
    assert resolved.grpc is not None
    assert resolved.grpc.proto_root == proto_root.resolve()
    assert resolved.grpc.include_paths == ((tmp_path / "includes").resolve(),)
    assert resolved.grpc.jobs[0].output == (tmp_path / "generated" / "python").resolve()
    assert resolved.grpc.jobs[0].include_paths == ((tmp_path / "job-includes").resolve(),)


def test_shared_example_config_lists_expected_grpc_jobs():
    assert [job.name for job in list_grpc_jobs(EXAMPLE_CONFIG)] == ["python.greeter", "go.greeter"]
