from __future__ import annotations

from scripts import example_validation
from tests.support import REPO_ROOT


def test_examples_regenerate_without_snapshot_drift_and_compile():
    example_validation.validate_examples(REPO_ROOT)
