from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .constants import PROJECT_ROOT
from .models import ExampleValidationError, ExampleValidationMode, ExampleValidationScope
from .runner import (
    compile_examples,
    refresh_examples,
    run_golang_suite_examples,
    run_java_suite_examples,
    validate_examples,
)

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate or refresh generated example snapshots. "
            "Use `check` for strict snapshot validation, `compile` when drift is expected, "
            "and `refresh` to accept regenerated snapshots."
        )
    )
    parser.add_argument("--repo-root", default=str(PROJECT_ROOT), help="Repository root containing examples/")
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in ExampleValidationMode],
        default=ExampleValidationMode.CHECK.value,
        help=(
            "Validation mode: `check` fails on snapshot drift, "
            "`compile` skips snapshot diff and only checks regenerated outputs compile, "
            "`refresh` regenerates examples in-place and compiles them, "
            "`golang-suite` runs the manual generated Go client/server round-trip suite, "
            "and `java-suite` runs the manual generated Java Spring contract-boundary smoke suite."
        ),
    )
    parser.add_argument(
        "--scope",
        choices=[scope.value for scope in ExampleValidationScope],
        default=ExampleValidationScope.ALL.value,
        help=(
            "Example scope: `all` validates every example, while `blueprint`, `grpc`, "
            "or `wails-hello` restrict tooling checks and validation to that example family."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        repo_root = Path(args.repo_root).resolve()
        mode = ExampleValidationMode(args.mode)
        scope = ExampleValidationScope(args.scope)
        if mode is ExampleValidationMode.CHECK:
            validate_examples(repo_root, scope=scope)
        elif mode is ExampleValidationMode.COMPILE:
            compile_examples(repo_root, scope=scope)
        elif mode is ExampleValidationMode.GOLANG_SUITE:
            run_golang_suite_examples(repo_root, scope=scope)
        elif mode is ExampleValidationMode.JAVA_SUITE:
            run_java_suite_examples(repo_root, scope=scope)
        else:
            refresh_examples(repo_root, scope=scope)
    except (ExampleValidationError, FileNotFoundError, ModuleNotFoundError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0
