from __future__ import annotations

import filecmp
from collections.abc import Iterable, Mapping
from pathlib import Path

from .connection_contract import _validate_blueprint_connection_examples
from .constants import EXAMPLE_SNAPSHOT_IGNORES
from .models import BlueprintExampleWorkspace, ExampleValidationError, GrpcExampleWorkspace, WailsHelloExampleWorkspace

SnapshotIgnoreMap = Mapping[str, frozenset[str]]

GO_SERVER_TARGET_SNAPSHOT_IGNORES: SnapshotIgnoreMap = {
    "blueprint/golang/server/views/transports": frozenset(("wailsv2", "wailsv3")),
}

def validate_example_snapshots(repo_root: Path, workspace: BlueprintExampleWorkspace) -> None:
    examples_root = repo_root / "examples"
    _raise_on_snapshot_drift(
        (
            (examples_root / "api-blueprint.index.json", workspace.root / "api-blueprint.index.json", "contract/index"),
            (examples_root / "golang", workspace.golang_dir, "blueprint/golang"),
            (examples_root / "typescript", workspace.typescript_dir, "blueprint/typescript"),
            (examples_root / "kotlin", workspace.kotlin_dir, "blueprint/kotlin"),
            (examples_root / "java", workspace.java_dir, "blueprint/java"),
            (examples_root / "python", workspace.python_dir, "blueprint/python"),
            (examples_root / "flutter", workspace.flutter_dir, "blueprint/flutter"),
            (examples_root / "swift", workspace.swift_dir, "blueprint/swift"),
        )
    )
    _validate_blueprint_connection_examples(workspace)


def validate_blueprint_go_server_snapshots(repo_root: Path, workspace: BlueprintExampleWorkspace) -> None:
    examples_root = repo_root / "examples"
    _raise_on_snapshot_drift(
        (
            (examples_root / "golang" / "server", workspace.golang_server_dir, "blueprint/golang/server"),
        ),
        ignores=GO_SERVER_TARGET_SNAPSHOT_IGNORES,
    )


def validate_grpc_snapshots(repo_root: Path, workspace: GrpcExampleWorkspace) -> None:
    example_root = repo_root / "examples" / "grpc"
    _raise_on_snapshot_drift(
        (
            (example_root / "protos", workspace.protos_dir, "grpc/protos"),
            (example_root / "go", workspace.go_dir, "grpc/go"),
            (example_root / "python", workspace.python_dir, "grpc/python"),
        )
    )


def validate_wails_hello_snapshots(repo_root: Path, workspace: WailsHelloExampleWorkspace) -> None:
    example_root = repo_root / "examples" / "wails-hello"
    _raise_on_snapshot_drift(
        (
            (example_root / "golang", workspace.golang_dir, "wails-hello/golang"),
            (example_root / "typescript", workspace.typescript_dir, "wails-hello/typescript"),
        )
    )


def _raise_on_snapshot_drift(
    pairs: Iterable[tuple[Path, Path, str]],
    *,
    ignores: SnapshotIgnoreMap = EXAMPLE_SNAPSHOT_IGNORES,
) -> None:
    problems: list[str] = []
    for expected, actual, label in pairs:
        problems.extend(_collect_path_diff(expected, actual, prefix=label, ignores=ignores))
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


def _collect_path_diff(
    expected: Path,
    actual: Path,
    prefix: str = "",
    *,
    ignores: SnapshotIgnoreMap = EXAMPLE_SNAPSHOT_IGNORES,
) -> list[str]:
    label = prefix or expected.name
    if expected.is_dir():
        if not actual.is_dir():
            return [f"{label}: missing directory"]
        return _collect_dir_diff(expected, actual, prefix=label, ignores=ignores)
    if expected.is_file():
        if not actual.is_file():
            return [f"{label}: missing file"]
        if expected.read_bytes() != actual.read_bytes():
            return [f"{label}: changed file"]
        return []
    if actual.exists():
        return [f"{label}: unexpected {actual.name}"]
    return []

def _collect_dir_diff(
    expected: Path,
    actual: Path,
    prefix: str = "",
    *,
    ignores: SnapshotIgnoreMap = EXAMPLE_SNAPSHOT_IGNORES,
) -> list[str]:
    comparison = filecmp.dircmp(expected, actual)
    label = prefix or expected.name
    ignored = ignores.get(label, frozenset())
    left_only = [name for name in comparison.left_only if name not in ignored]
    right_only = [name for name in comparison.right_only if name not in ignored]
    problems = [f"{label}: missing {name}" for name in left_only]
    problems += [f"{label}: unexpected {name}" for name in right_only]
    problems += [f"{label}: changed {name}" for name in comparison.diff_files]
    problems += [f"{label}: unreadable {name}" for name in comparison.funny_files]
    for child in comparison.common_dirs:
        if child in ignored:
            continue
        child_prefix = f"{label}/{child}" if label else child
        problems.extend(_collect_dir_diff(expected / child, actual / child, child_prefix, ignores=ignores))
    return problems
