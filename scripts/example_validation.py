#!/usr/bin/env python3

from __future__ import annotations

import argparse
import filecmp
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Iterable, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from api_blueprint.application.generation import generate_golang, generate_grpc, generate_typescript

PROTOC_GEN_GO_VERSION = "v1.36.10"
PROTOC_GEN_GO_GRPC_VERSION = "v1.6.0"
GO_ENUM_VERSION = "v0.9.2"

BLUEPRINT_GOLANG_PRESERVED = (
    "go.mod",
    "go.sum",
    "main.go",
)
BLUEPRINT_TYPESCRIPT_PRESERVED = (
    ".vscode/settings.json",
    "index.ts",
    "tsconfig.json",
)
GRPC_GO_PRESERVED = ("go.mod",)


class ExampleValidationError(RuntimeError):
    pass


class ExampleValidationMode(StrEnum):
    CHECK = "check"
    COMPILE = "compile"
    REFRESH = "refresh"


@dataclass(frozen=True)
class BlueprintExampleWorkspace:
    root: Path
    config_path: Path
    golang_dir: Path
    typescript_dir: Path


@dataclass(frozen=True)
class GrpcExampleWorkspace:
    root: Path
    config_path: Path
    go_dir: Path
    python_dir: Path


def collect_missing_validation_requirements() -> tuple[str, ...]:
    requirements = (
        (
            "tsc",
            "install the TypeScript CLI, for example `npm install --global typescript`.",
        ),
        (
            "go",
            "install Go and ensure `go` is available on PATH.",
        ),
        (
            "go-enum",
            "install it with `go install github.com/abice/go-enum@"
            + GO_ENUM_VERSION
            + "`.",
        ),
        (
            "protoc",
            "install the Protocol Buffers compiler, for example `brew install protobuf` or `apt-get install protobuf-compiler`.",
        ),
        (
            "protoc-gen-go",
            "install it with `go install google.golang.org/protobuf/cmd/protoc-gen-go@"
            + PROTOC_GEN_GO_VERSION
            + "`.",
        ),
        (
            "protoc-gen-go-grpc",
            "install it with `go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@"
            + PROTOC_GEN_GO_GRPC_VERSION
            + "`.",
        ),
    )

    missing: list[str] = []
    for name, guidance in requirements:
        if shutil.which(name) is None:
            missing.append(f"{name}: {guidance}")

    if importlib.util.find_spec("grpc_tools") is None:
        missing.append(
            "grpc_tools: install Python dev dependencies with `uv sync --dev` or install `grpcio-tools` manually."
        )

    return tuple(missing)


def ensure_validation_requirements() -> None:
    missing = collect_missing_validation_requirements()
    if not missing:
        return
    raise ExampleValidationError(
        "example validation requires additional tooling:\n"
        + "\n".join(f"- {item}" for item in missing)
    )


def _blueprint_workspace(root: Path) -> BlueprintExampleWorkspace:
    return BlueprintExampleWorkspace(
        root=root,
        config_path=root / "api-blueprint.toml",
        golang_dir=root / "golang",
        typescript_dir=root / "typescript",
    )


def _grpc_workspace(root: Path) -> GrpcExampleWorkspace:
    return GrpcExampleWorkspace(
        root=root,
        config_path=root / "api-blueprint.toml",
        go_dir=root / "grpc" / "go",
        python_dir=root / "grpc" / "python",
    )


def prepare_blueprint_workspace(repo_root: Path) -> BlueprintExampleWorkspace:
    examples_root = repo_root / "examples"
    workspace_root = Path(tempfile.mkdtemp(prefix="api-blueprint-blueprint-examples-"))
    shutil.copytree(examples_root / "blueprints", workspace_root / "blueprints")
    shutil.copy2(examples_root / "api-blueprint.toml", workspace_root / "api-blueprint.toml")
    _prepare_blueprint_outputs(source_root=examples_root, target_root=workspace_root)
    return _blueprint_workspace(workspace_root)


def prepare_grpc_workspace(repo_root: Path) -> GrpcExampleWorkspace:
    examples_root = repo_root / "examples"
    workspace_root = Path(tempfile.mkdtemp(prefix="api-blueprint-grpc-examples-"))
    shutil.copytree(examples_root / "grpc" / "protos", workspace_root / "grpc" / "protos")
    shutil.copy2(examples_root / "api-blueprint.toml", workspace_root / "api-blueprint.toml")
    _prepare_grpc_outputs(source_root=examples_root / "grpc", target_root=workspace_root / "grpc")
    return _grpc_workspace(workspace_root)


def _prepare_blueprint_outputs(*, source_root: Path, target_root: Path) -> None:
    _prepare_output_dir(
        target_root / "golang",
        _capture_relative_files(source_root / "golang", BLUEPRINT_GOLANG_PRESERVED),
    )
    _prepare_output_dir(
        target_root / "typescript",
        _capture_relative_files(source_root / "typescript", BLUEPRINT_TYPESCRIPT_PRESERVED),
    )


def _prepare_grpc_outputs(*, source_root: Path, target_root: Path) -> None:
    _prepare_output_dir(
        target_root / "go",
        _capture_relative_files(source_root / "go", GRPC_GO_PRESERVED),
    )
    _prepare_output_dir(target_root / "python", {})


def _capture_relative_files(root: Path, relative_paths: Iterable[str]) -> dict[Path, bytes]:
    captured: dict[Path, bytes] = {}
    for relative in relative_paths:
        relative_path = Path(relative)
        file_path = root / relative_path
        if not file_path.is_file():
            continue
        captured[relative_path] = file_path.read_bytes()
    return captured


def _prepare_output_dir(root: Path, preserved_files: Mapping[Path, bytes]) -> None:
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    for relative_path, data in preserved_files.items():
        file_path = root / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(data)


def regenerate_blueprint_examples(workspace: BlueprintExampleWorkspace) -> None:
    generate_typescript(workspace.config_path)
    generate_golang(workspace.config_path)


def regenerate_grpc_examples(workspace: GrpcExampleWorkspace) -> None:
    generate_grpc(workspace.config_path)
    _tidy_go_module(workspace.go_dir)


def regenerate_repo_blueprint_examples(repo_root: Path) -> None:
    examples_root = repo_root / "examples"
    _prepare_blueprint_outputs(source_root=examples_root, target_root=examples_root)
    regenerate_blueprint_examples(_blueprint_workspace(examples_root))


def regenerate_repo_grpc_examples(repo_root: Path) -> None:
    example_root = repo_root / "examples" / "grpc"
    _prepare_grpc_outputs(source_root=example_root, target_root=example_root)
    regenerate_grpc_examples(_grpc_workspace(repo_root / "examples"))


def validate_example_snapshots(repo_root: Path, workspace: BlueprintExampleWorkspace) -> None:
    examples_root = repo_root / "examples"
    _raise_on_snapshot_drift(
        (
            (examples_root / "golang", workspace.golang_dir, "blueprint/golang"),
            (examples_root / "typescript", workspace.typescript_dir, "blueprint/typescript"),
        )
    )


def validate_grpc_snapshots(repo_root: Path, workspace: GrpcExampleWorkspace) -> None:
    example_root = repo_root / "examples" / "grpc"
    _raise_on_snapshot_drift(
        (
            (example_root / "go", workspace.go_dir, "grpc/go"),
            (example_root / "python", workspace.python_dir, "grpc/python"),
        )
    )


def _raise_on_snapshot_drift(pairs: Iterable[tuple[Path, Path, str]]) -> None:
    problems: list[str] = []
    for expected, actual, label in pairs:
        problems.extend(_collect_dir_diff(expected, actual, prefix=label))
    if not problems:
        return

    raise ExampleValidationError(
        "example snapshot drift detected:\n"
        + "\n".join(problems)
        + "\n\n"
        + "Snapshot drift is not automatically a bug. If the generator change is intentional, "
        + "refresh and review the committed examples with `make example-refresh` or "
        + "`uv run python scripts/example_validation.py --mode refresh`."
    )


def compile_generated_examples(workspace: BlueprintExampleWorkspace) -> None:
    subprocess.run(["tsc", "-p", str(workspace.typescript_dir / "tsconfig.json"), "--noEmit"], check=True)
    subprocess.run(["go", "test", "./..."], cwd=workspace.golang_dir, check=True)


def compile_generated_grpc_examples(workspace: GrpcExampleWorkspace) -> None:
    _run_python_grpc_import_smoke(workspace.python_dir)
    subprocess.run(["go", "test", "./..."], cwd=workspace.go_dir, check=True)


def compile_repo_examples(repo_root: Path) -> None:
    compile_generated_examples(_blueprint_workspace(repo_root / "examples"))


def compile_repo_grpc_examples(repo_root: Path) -> None:
    compile_generated_grpc_examples(_grpc_workspace(repo_root / "examples"))


def _tidy_go_module(go_dir: Path) -> None:
    subprocess.run(["go", "mod", "tidy"], cwd=go_dir, check=True)


def _run_python_grpc_import_smoke(python_dir: Path) -> None:
    env = os.environ.copy()
    python_path = str(python_dir)
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = python_path if not existing else python_path + os.pathsep + existing
    smoke = (
        "import examplegrpc_pb.commonpb.common_pb2\n"
        "import examplegrpc_pb.greeterpb.greeter_pb2\n"
        "import examplegrpc_pb.greeterpb.greeter_pb2_grpc\n"
    )
    subprocess.run([sys.executable, "-c", smoke], env=env, check=True)


def validate_examples(repo_root: Path) -> None:
    ensure_validation_requirements()
    blueprint_workspace = prepare_blueprint_workspace(repo_root)
    grpc_workspace = prepare_grpc_workspace(repo_root)
    try:
        regenerate_blueprint_examples(blueprint_workspace)
        regenerate_grpc_examples(grpc_workspace)
        validate_example_snapshots(repo_root, blueprint_workspace)
        validate_grpc_snapshots(repo_root, grpc_workspace)
        compile_generated_examples(blueprint_workspace)
        compile_generated_grpc_examples(grpc_workspace)
    finally:
        shutil.rmtree(blueprint_workspace.root, ignore_errors=True)
        shutil.rmtree(grpc_workspace.root, ignore_errors=True)


def compile_examples(repo_root: Path) -> None:
    ensure_validation_requirements()
    blueprint_workspace = prepare_blueprint_workspace(repo_root)
    grpc_workspace = prepare_grpc_workspace(repo_root)
    try:
        regenerate_blueprint_examples(blueprint_workspace)
        regenerate_grpc_examples(grpc_workspace)
        compile_generated_examples(blueprint_workspace)
        compile_generated_grpc_examples(grpc_workspace)
    finally:
        shutil.rmtree(blueprint_workspace.root, ignore_errors=True)
        shutil.rmtree(grpc_workspace.root, ignore_errors=True)


def refresh_examples(repo_root: Path) -> None:
    ensure_validation_requirements()
    regenerate_repo_blueprint_examples(repo_root)
    regenerate_repo_grpc_examples(repo_root)
    compile_repo_examples(repo_root)
    compile_repo_grpc_examples(repo_root)


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
            "`refresh` regenerates examples in-place and compiles them."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        repo_root = Path(args.repo_root).resolve()
        mode = ExampleValidationMode(args.mode)
        if mode is ExampleValidationMode.CHECK:
            validate_examples(repo_root)
        elif mode is ExampleValidationMode.COMPILE:
            compile_examples(repo_root)
        else:
            refresh_examples(repo_root)
    except (ExampleValidationError, FileNotFoundError, ModuleNotFoundError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
