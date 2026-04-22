from __future__ import annotations

from api_blueprint.config import Config
from tests.support import EXAMPLE_CONFIG


def test_example_config_loads_expected_values():
    config = Config.load(EXAMPLE_CONFIG)

    assert config.blueprint.entrypoints == ["blueprints.app:*"]
    assert config.blueprint.docs_server == "0.0.0.0:2332"
    assert config.golang.codegen_output == "golang"
    assert config.typescript is not None
    assert config.typescript.codegen_output == "typescript"
    assert config.typescript.base_url == "http://localhost:2333"
