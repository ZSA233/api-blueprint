from __future__ import annotations

import pytest

from api_blueprint.config import Config, resolve_config

from api_blueprint.application.generator import target_manifest

from tests.support import EXAMPLE_CONFIG

__all__ = [name for name in globals() if not name.startswith('__') or name == '__version__']
