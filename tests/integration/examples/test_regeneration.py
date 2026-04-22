from __future__ import annotations

import shutil

import pytest

from scripts import example_validation
from tests.support import REPO_ROOT

pytestmark = pytest.mark.example_validation


def test_examples_regenerate_without_snapshot_drift_and_compile():
    missing = [tool for tool in ("tsc", "go") if shutil.which(tool) is None]
    if missing:
        pytest.skip(f"example validation requires external toolchains: {', '.join(missing)}")
    example_validation.validate_examples(REPO_ROOT)
