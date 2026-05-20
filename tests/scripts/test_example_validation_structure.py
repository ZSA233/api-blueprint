from __future__ import annotations

import importlib
import subprocess
import sys

from tests.support import REPO_ROOT


def test_example_validation_is_package_with_compatibility_exports() -> None:
    module = importlib.import_module("scripts.example_validation")

    assert module.__path__
    assert module.ExampleValidationScope.BLUEPRINT.value == "blueprint"
    assert callable(module.validate_examples)
    assert callable(module._prepare_blueprint_outputs)


def test_example_validation_legacy_script_entrypoint_still_works() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/example_validation.py", "--help"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Validate or refresh generated example snapshots" in result.stdout
    assert "--scope" in result.stdout
