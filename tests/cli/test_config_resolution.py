from __future__ import annotations

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


def test_resolve_config_converts_relative_outputs_to_absolute_paths():
    resolved = resolve_config(EXAMPLE_CONFIG)
    assert resolved.golang.output is not None
    assert resolved.golang.output.is_absolute()
    assert resolved.typescript is not None
    assert resolved.typescript.output is not None
    assert resolved.typescript.output.is_absolute()
