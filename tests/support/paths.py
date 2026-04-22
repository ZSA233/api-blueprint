from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
EXAMPLES_DIR = REPO_ROOT / "examples"
EXAMPLE_CONFIG = EXAMPLES_DIR / "api-blueprint.toml"

for path in (REPO_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
