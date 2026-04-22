from __future__ import annotations

import sys

from tests.support.paths import EXAMPLE_CONFIG, EXAMPLES_DIR


def reset_example_modules() -> None:
    from api_blueprint.engine import reset_shared_app

    reset_shared_app()
    for name in list(sys.modules):
        if name == "blueprints" or name.startswith("blueprints."):
            sys.modules.pop(name)


def load_example_entrypoints():
    from api_blueprint.config import Config
    from api_blueprint.helper import load_entrypoints

    reset_example_modules()
    config = Config.load(EXAMPLE_CONFIG)
    entrypoints = load_entrypoints(config.blueprint.entrypoints, EXAMPLES_DIR)
    return config, entrypoints
