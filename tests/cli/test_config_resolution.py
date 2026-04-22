from __future__ import annotations

import pytest

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
    assert config.typescript.base_url_expr is None
    assert config.grpc is not None
    assert [job.name for job in config.grpc.jobs] == ["python.greeter", "go.greeter"]


def test_resolve_config_converts_relative_outputs_to_absolute_paths():
    resolved = resolve_config(EXAMPLE_CONFIG)
    assert resolved.golang.output is not None
    assert resolved.golang.output.is_absolute()
    assert resolved.typescript is not None
    assert resolved.typescript.output is not None
    assert resolved.typescript.output.is_absolute()
    assert resolved.typescript.base_url_expr is None
    assert resolved.grpc is not None
    assert resolved.grpc.proto_root == (EXAMPLE_CONFIG.parent / "grpc" / "protos").resolve()
    assert resolved.grpc.jobs[0].output == (EXAMPLE_CONFIG.parent / "grpc" / "python").resolve()
    assert resolved.grpc.jobs[1].output == (EXAMPLE_CONFIG.parent / "grpc" / "go").resolve()
    assert resolved.grpc.jobs[0].proto_root == (EXAMPLE_CONFIG.parent / "grpc" / "protos").resolve()
    assert resolved.grpc.jobs[1].proto_root == (EXAMPLE_CONFIG.parent / "grpc" / "protos").resolve()
    assert resolved.grpc.jobs[0].layout == "source_relative"
    assert resolved.grpc.jobs[0].module is None
    assert resolved.grpc.jobs[1].layout == "source_relative"
    assert resolved.grpc.jobs[1].module is None


def test_typescript_base_url_expr_loads_and_resolves(tmp_path):
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[typescript]
codegen_output = "typescript"
base_url_expr = "import.meta.env.VITE_API_BASE_URL"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = Config.load(config_path)
    assert config.typescript is not None
    assert config.typescript.base_url is None
    assert config.typescript.base_url_expr == "import.meta.env.VITE_API_BASE_URL"

    resolved = resolve_config(config_path)
    assert resolved.typescript is not None
    assert resolved.typescript.base_url is None
    assert resolved.typescript.base_url_expr == "import.meta.env.VITE_API_BASE_URL"


def test_typescript_base_url_and_expr_are_mutually_exclusive(tmp_path):
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[typescript]
codegen_output = "typescript"
base_url = "http://localhost:2333"
base_url_expr = "import.meta.env.VITE_API_BASE_URL"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="mutually exclusive"):
        Config.load(config_path)


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
    assert resolved.grpc.jobs[0].proto_root == proto_root.resolve()
    assert resolved.grpc.jobs[0].include_paths == ((tmp_path / "job-includes").resolve(),)
    assert resolved.grpc.jobs[0].layout == "source_relative"
    assert resolved.grpc.jobs[0].module is None


def test_grpc_job_proto_root_override_loads_and_resolves_absolute_paths(tmp_path):
    global_proto_root = tmp_path / "protos"
    global_proto_root.mkdir(parents=True)
    service_proto_root = global_proto_root / "services" / "exampledomain" / "api"
    service_proto_root.mkdir(parents=True)

    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[grpc]
proto_root = "protos"
include_paths = ["includes"]

[[grpc.jobs]]
name = "python.shared"
preset = "python"
output = "generated/python"
protos = ["shared/**/*.proto"]

[[grpc.jobs]]
name = "python.services"
preset = "python"
output = "generated/python"
proto_root = "protos/services/exampledomain/api"
protos = ["feature/v1/example.proto"]
include_paths = ["job-includes"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = Config.load(config_path)
    assert config.grpc is not None
    assert config.grpc.jobs[0].proto_root is None
    assert config.grpc.jobs[1].proto_root == "protos/services/exampledomain/api"

    resolved = resolve_config(config_path)
    assert resolved.grpc is not None
    assert resolved.grpc.proto_root == global_proto_root.resolve()
    assert resolved.grpc.jobs[0].proto_root == global_proto_root.resolve()
    assert resolved.grpc.jobs[1].proto_root == service_proto_root.resolve()
    assert resolved.grpc.jobs[1].include_paths == ((tmp_path / "job-includes").resolve(),)


def test_grpc_go_package_layout_loads_and_resolves_absolute_paths(tmp_path):
    proto_root = tmp_path / "protos"
    proto_root.mkdir()

    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[grpc]
proto_root = "protos"

[[grpc.jobs]]
name = "go.browser"
preset = "go"
output = "generated/go"
protos = ["browser.proto"]
layout = "go_package"
module = "examplemod"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = Config.load(config_path)
    assert config.grpc is not None
    assert config.grpc.jobs[0].layout == "go_package"
    assert config.grpc.jobs[0].module == "examplemod"

    resolved = resolve_config(config_path)
    assert resolved.grpc is not None
    assert resolved.grpc.jobs[0].output == (tmp_path / "generated" / "go").resolve()
    assert resolved.grpc.jobs[0].proto_root == proto_root.resolve()
    assert resolved.grpc.jobs[0].layout == "go_package"
    assert resolved.grpc.jobs[0].module == "examplemod"


def test_grpc_python_job_rejects_go_package_layout(tmp_path):
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[grpc]
proto_root = "protos"

[[grpc.jobs]]
name = "python.greeter"
preset = "python"
output = "generated/python"
protos = ["**/*.proto"]
layout = "go_package"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="layout=go_package"):
        Config.load(config_path)


def test_grpc_python_job_rejects_module(tmp_path):
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[grpc]
proto_root = "protos"

[[grpc.jobs]]
name = "python.greeter"
preset = "python"
output = "generated/python"
protos = ["**/*.proto"]
module = "examplemod"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="do not support module"):
        Config.load(config_path)


def test_grpc_go_job_rejects_module_without_go_package_layout(tmp_path):
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[grpc]
proto_root = "protos"

[[grpc.jobs]]
name = "go.greeter"
preset = "go"
output = "generated/go"
protos = ["greeter.proto"]
module = "examplemod"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="layout=go_package"):
        Config.load(config_path)


def test_shared_example_config_lists_expected_grpc_jobs():
    assert [job.name for job in list_grpc_jobs(EXAMPLE_CONFIG)] == ["python.greeter", "go.greeter"]
