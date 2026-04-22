from __future__ import annotations

import pytest

from api_blueprint.application.generation import list_grpc_jobs, list_grpc_targets
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
    assert [target.id for target in config.grpc.targets] == ["python.greeter", "go.greeter"]
    assert config.grpc.jobs == []


def test_resolve_config_converts_relative_outputs_to_absolute_paths():
    resolved = resolve_config(EXAMPLE_CONFIG)
    assert resolved.golang.output is not None
    assert resolved.golang.output.is_absolute()
    assert resolved.typescript is not None
    assert resolved.typescript.output is not None
    assert resolved.typescript.output.is_absolute()
    assert resolved.typescript.base_url_expr is None
    assert resolved.grpc is not None
    assert resolved.grpc.source_root == (EXAMPLE_CONFIG.parent / "grpc" / "protos").resolve()
    assert resolved.grpc.targets[0].out_dir == (EXAMPLE_CONFIG.parent / "grpc" / "python").resolve()
    assert resolved.grpc.targets[1].out_dir == (EXAMPLE_CONFIG.parent / "grpc" / "go").resolve()
    assert resolved.grpc.targets[0].source_root == (EXAMPLE_CONFIG.parent / "grpc" / "protos").resolve()
    assert resolved.grpc.targets[1].source_root == (EXAMPLE_CONFIG.parent / "grpc" / "protos").resolve()
    assert resolved.grpc.targets[0].import_roots == ()
    assert resolved.grpc.targets[1].import_roots == ()
    assert resolved.grpc.jobs == ()


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


def test_grpc_targets_load_and_resolve_absolute_paths(tmp_path):
    proto_root = tmp_path / "protos"
    proto_root.mkdir()

    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[grpc]
source_root = "protos"
import_roots = ["includes"]

[[grpc.targets]]
id = "python.greeter"
lang = "python"
out_dir = "generated/python"
files = ["**/*.proto"]
import_roots = ["job-includes"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = Config.load(config_path)
    assert config.blueprint is None
    assert config.golang is None
    assert config.typescript is None
    assert config.grpc is not None
    assert config.grpc.targets[0].id == "python.greeter"

    resolved = resolve_config(config_path)
    assert resolved.golang is None
    assert resolved.typescript is None
    assert resolved.grpc is not None
    assert resolved.grpc.source_root == proto_root.resolve()
    assert resolved.grpc.import_roots == ((tmp_path / "includes").resolve(),)
    assert resolved.grpc.targets[0].out_dir == (tmp_path / "generated" / "python").resolve()
    assert resolved.grpc.targets[0].source_root == proto_root.resolve()
    assert resolved.grpc.targets[0].import_roots == ((tmp_path / "job-includes").resolve(),)


def test_grpc_targets_can_override_source_root_and_append_import_roots(tmp_path):
    global_source_root = tmp_path / "protos"
    global_source_root.mkdir(parents=True)
    service_source_root = global_source_root / "services" / "exampledomain" / "api"
    service_source_root.mkdir(parents=True)

    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[grpc]
source_root = "protos"
import_roots = ["includes"]

[[grpc.targets]]
id = "python.shared"
lang = "python"
out_dir = "generated/python"
files = ["shared/**/*.proto"]

[[grpc.targets]]
id = "python.services"
lang = "python"
out_dir = "generated/python"
source_root = "protos/services/exampledomain/api"
files = ["feature/v1/example.proto"]
import_roots = ["job-includes"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = Config.load(config_path)
    assert config.grpc is not None
    assert config.grpc.targets[0].source_root is None
    assert config.grpc.targets[1].source_root == "protos/services/exampledomain/api"

    resolved = resolve_config(config_path)
    assert resolved.grpc is not None
    assert resolved.grpc.source_root == global_source_root.resolve()
    assert resolved.grpc.targets[0].source_root == global_source_root.resolve()
    assert resolved.grpc.targets[1].source_root == service_source_root.resolve()
    assert resolved.grpc.targets[1].import_roots == ((tmp_path / "job-includes").resolve(),)


def test_grpc_targets_inherit_legacy_globals_when_new_globals_are_absent(tmp_path):
    proto_root = tmp_path / "protos"
    proto_root.mkdir()

    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[grpc]
proto_root = "protos"
include_paths = ["includes"]

[[grpc.targets]]
id = "go.greeter"
lang = "go"
out_dir = "generated/go"
files = ["greeter.proto"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    resolved = resolve_config(config_path)
    assert resolved.grpc is not None
    assert resolved.grpc.source_root == proto_root.resolve()
    assert resolved.grpc.import_roots == ((tmp_path / "includes").resolve(),)
    assert resolved.grpc.targets[0].source_root == proto_root.resolve()


def test_grpc_legacy_jobs_still_load_and_resolve_absolute_paths(tmp_path):
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
    assert config.grpc is not None
    assert config.grpc.jobs[0].name == "python.greeter"

    resolved = resolve_config(config_path)
    assert resolved.grpc is not None
    assert resolved.grpc.proto_root == proto_root.resolve()
    assert resolved.grpc.include_paths == ((tmp_path / "includes").resolve(),)
    assert resolved.grpc.jobs[0].output == (tmp_path / "generated" / "python").resolve()
    assert resolved.grpc.jobs[0].proto_root == proto_root.resolve()
    assert resolved.grpc.jobs[0].include_paths == ((tmp_path / "job-includes").resolve(),)
    assert resolved.grpc.jobs[0].layout == "source_relative"
    assert resolved.grpc.jobs[0].module is None


def test_grpc_targets_and_jobs_can_mix(tmp_path):
    proto_root = tmp_path / "protos"
    proto_root.mkdir()

    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[grpc]
source_root = "protos"

[[grpc.targets]]
id = "python.greeter"
lang = "python"
out_dir = "generated/python"
files = ["**/*.proto"]

[[grpc.jobs]]
name = "legacy.go.greeter"
preset = "go"
output = "generated/go"
protos = ["greeter.proto"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    resolved = resolve_config(config_path)
    assert resolved.grpc is not None
    assert [target.id for target in resolved.grpc.targets] == ["python.greeter"]
    assert [job.name for job in resolved.grpc.jobs] == ["legacy.go.greeter"]
    assert resolved.grpc.targets[0].source_root == proto_root.resolve()
    assert resolved.grpc.jobs[0].proto_root == proto_root.resolve()


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


def test_shared_example_config_lists_expected_grpc_targets():
    assert [target.id for target in list_grpc_targets(EXAMPLE_CONFIG)] == ["python.greeter", "go.greeter"]
    assert list_grpc_jobs(EXAMPLE_CONFIG) == ()
