from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
EXAMPLES_DIR = REPO_ROOT / "examples"
EXAMPLE_CONFIG = EXAMPLES_DIR / "api-blueprint.toml"

for path in (REPO_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def reset_example_modules() -> None:
    import api_blueprint.engine as engine

    engine.__GLOBAL_APP__ = None
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
