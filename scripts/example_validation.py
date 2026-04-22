#!/usr/bin/env python3

from __future__ import annotations

import argparse
import filecmp
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from api_blueprint.application.generation import generate_golang, generate_typescript


class ExampleValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExampleWorkspace:
    root: Path
    config_path: Path
    golang_dir: Path
    typescript_dir: Path


def prepare_workspace(repo_root: Path) -> ExampleWorkspace:
    examples_root = repo_root / "examples"
    workspace_root = Path(tempfile.mkdtemp(prefix="api-blueprint-examples-"))
    shutil.copytree(examples_root / "blueprints", workspace_root / "blueprints")
    shutil.copytree(examples_root / "golang", workspace_root / "golang")
    shutil.copytree(examples_root / "typescript", workspace_root / "typescript")
    shutil.copy2(examples_root / "api-blueprint.toml", workspace_root / "api-blueprint.toml")
    return ExampleWorkspace(
        root=workspace_root,
        config_path=workspace_root / "api-blueprint.toml",
        golang_dir=workspace_root / "golang",
        typescript_dir=workspace_root / "typescript",
    )


def regenerate_examples(repo_root: Path, workspace: ExampleWorkspace) -> None:
    generate_typescript(workspace.config_path)
    generate_golang(workspace.config_path)


def validate_example_snapshots(repo_root: Path, workspace: ExampleWorkspace) -> None:
    examples_root = repo_root / "examples"
    problems = []
    problems.extend(_collect_dir_diff(examples_root / "golang", workspace.golang_dir))
    problems.extend(_collect_dir_diff(examples_root / "typescript", workspace.typescript_dir))
    if problems:
        raise ExampleValidationError("example snapshot drift detected:\n" + "\n".join(problems))


def compile_generated_examples(workspace: ExampleWorkspace) -> None:
    subprocess.run(["tsc", "-p", str(workspace.typescript_dir / "tsconfig.json"), "--noEmit"], check=True)
    subprocess.run(["go", "test", "./..."], cwd=workspace.golang_dir, check=True)


def validate_examples(repo_root: Path) -> None:
    workspace = prepare_workspace(repo_root)
    try:
        regenerate_examples(repo_root, workspace)
        validate_example_snapshots(repo_root, workspace)
        compile_generated_examples(workspace)
    finally:
        shutil.rmtree(workspace.root, ignore_errors=True)


def _collect_dir_diff(expected: Path, actual: Path, prefix: str = "") -> list[str]:
    comparison = filecmp.dircmp(expected, actual)
    label = prefix or expected.name
    problems = [f"{label}: missing {name}" for name in comparison.left_only]
    problems += [f"{label}: unexpected {name}" for name in comparison.right_only]
    problems += [f"{label}: changed {name}" for name in comparison.diff_files]
    problems += [f"{label}: unreadable {name}" for name in comparison.funny_files]
    for child in comparison.common_dirs:
        child_prefix = f"{label}/{child}" if label else child
        problems.extend(_collect_dir_diff(expected / child, actual / child, child_prefix))
    return problems


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate regenerated example snapshots and compile checks.")
    parser.add_argument("--repo-root", default=str(PROJECT_ROOT), help="Repository root containing examples/")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        validate_examples(Path(args.repo_root).resolve())
    except (ExampleValidationError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
