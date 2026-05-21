from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_benchmark_binary_script_exposes_all_targets() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "benchmark_binary.py"), "--help"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    help_text = result.stdout + result.stderr
    assert "--target" in help_text
    assert "go,typescript,python,kotlin,java,all" in help_text
    assert "--count" in help_text


def test_benchmark_binary_wrapper_uses_package_cli() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = (repo_root / "scripts" / "benchmark_binary.py").read_text(encoding="utf-8")

    assert "scripts.example_benchmark.binary" in script
    assert "from scripts.example_benchmark.binary import main" in script
