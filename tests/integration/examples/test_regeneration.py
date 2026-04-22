from __future__ import annotations

import pytest

from scripts import example_validation
from tests.support import REPO_ROOT

pytestmark = pytest.mark.example_validation


def test_examples_regenerate_without_snapshot_drift_and_compile():
    missing = example_validation.collect_missing_validation_requirements()
    if missing:
        pytest.skip("example validation requires external toolchains: " + "; ".join(missing))
    example_validation.validate_examples(REPO_ROOT)
