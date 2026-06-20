from __future__ import annotations

import filecmp
from collections.abc import Iterable, Mapping
from pathlib import Path

from .connection_contract import _validate_blueprint_connection_examples
from .constants import EXAMPLE_SNAPSHOT_IGNORES
from .models import (
    BlueprintExampleWorkspace,
    ExampleValidationError,
    ExampleValidationTarget,
    GrpcExampleWorkspace,
    WailsHelloExampleWorkspace,
)

SnapshotIgnoreMap = Mapping[str, frozenset[str]]

GO_SERVER_TARGET_SNAPSHOT_IGNORES: SnapshotIgnoreMap = {
    "blueprint/golang/server/views/transports": frozenset(("wailsv2", "wailsv3")),
}
TYPESCRIPT_CLIENT_TARGET_SNAPSHOT_IGNORES: SnapshotIgnoreMap = {
    **EXAMPLE_SNAPSHOT_IGNORES,
    "blueprint/typescript/alt/transports": frozenset(
        ("wailsv2", "wailsv3", "gen_clients.ts", "gen_index.ts", "clients.ts", "index.ts")
    ),
    "blueprint/typescript/api/transports": frozenset(
        ("wailsv2", "wailsv3", "gen_clients.ts", "gen_index.ts", "clients.ts", "index.ts")
    ),
    "blueprint/typescript/legacy/transports": frozenset(
        ("wailsv2", "wailsv3", "gen_clients.ts", "gen_index.ts", "clients.ts", "index.ts")
    ),
    "blueprint/typescript/runtime/transports": frozenset(
        ("wailsv2", "wailsv3", "gen_clients.ts", "gen_index.ts", "clients.ts", "index.ts")
    ),
    "blueprint/typescript/static/transports": frozenset(
        ("wailsv2", "wailsv3", "gen_clients.ts", "gen_index.ts", "clients.ts", "index.ts")
    ),
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


def validate_blueprint_target_snapshots(
    repo_root: Path,
    workspace: BlueprintExampleWorkspace,
    target: ExampleValidationTarget,
) -> None:
    if target is ExampleValidationTarget.GO_SERVER:
        validate_blueprint_go_server_snapshots(repo_root, workspace)
        return
    examples_root = repo_root / "examples"
    pairs_by_target: dict[ExampleValidationTarget, tuple[tuple[Path, Path, str], ...]] = {
        ExampleValidationTarget.GO_CLIENT: (
            (examples_root / "golang" / "client", workspace.golang_client_dir, "blueprint/golang/client"),
        ),
        ExampleValidationTarget.TYPESCRIPT_CLIENT: (
            (examples_root / "typescript", workspace.typescript_dir, "blueprint/typescript"),
        ),
        ExampleValidationTarget.PYTHON_HTTP: (
            (examples_root / "python", workspace.python_dir, "blueprint/python"),
        ),
        ExampleValidationTarget.KOTLIN_HTTP: (
            (examples_root / "kotlin", workspace.kotlin_dir, "blueprint/kotlin"),
        ),
        ExampleValidationTarget.JAVA_HTTP: (
            (examples_root / "java", workspace.java_dir, "blueprint/java"),
        ),
        ExampleValidationTarget.FLUTTER_CLIENT: (
            (examples_root / "flutter", workspace.flutter_dir, "blueprint/flutter"),
        ),
        ExampleValidationTarget.SWIFT_CLIENT: (
            (examples_root / "swift", workspace.swift_dir, "blueprint/swift"),
        ),
        ExampleValidationTarget.WAILS_BLUEPRINT: (
            (
                examples_root / "golang" / "server" / "views" / "transports" / "wailsv2",
                workspace.golang_server_dir / "views" / "transports" / "wailsv2",
                "blueprint/golang/server/views/transports/wailsv2",
            ),
            (
                examples_root / "golang" / "server" / "views" / "transports" / "wailsv3",
                workspace.golang_server_dir / "views" / "transports" / "wailsv3",
                "blueprint/golang/server/views/transports/wailsv3",
            ),
            (examples_root / "typescript", workspace.typescript_dir, "blueprint/typescript"),
        ),
    }
    try:
        pairs = pairs_by_target[target]
    except KeyError as exc:
        raise ValueError(f"target {target.value} is not a Blueprint example target") from exc
    ignores = TYPESCRIPT_CLIENT_TARGET_SNAPSHOT_IGNORES if target is ExampleValidationTarget.TYPESCRIPT_CLIENT else EXAMPLE_SNAPSHOT_IGNORES
    _raise_on_snapshot_drift(pairs, ignores=ignores)


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
    diff_files = [name for name in comparison.diff_files if name not in ignored]
    funny_files = [name for name in comparison.funny_files if name not in ignored]
    problems = [f"{label}: missing {name}" for name in left_only]
    problems += [f"{label}: unexpected {name}" for name in right_only]
    problems += [f"{label}: changed {name}" for name in diff_files]
    problems += [f"{label}: unreadable {name}" for name in funny_files]
    for child in comparison.common_dirs:
        if child in ignored:
            continue
        child_prefix = f"{label}/{child}" if label else child
        problems.extend(_collect_dir_diff(expected / child, actual / child, child_prefix, ignores=ignores))
    return problems
