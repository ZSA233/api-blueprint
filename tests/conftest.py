from __future__ import annotations

import pytest

from tests.support import load_example_entrypoints, reset_example_modules


@pytest.fixture()
def example_entrypoints():
    config, entrypoints = load_example_entrypoints()
    try:
        yield config, entrypoints
    finally:
        reset_example_modules()
