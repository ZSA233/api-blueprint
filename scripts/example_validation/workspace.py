from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path

from .constants import (
    BLUEPRINT_FLUTTER_PRESERVED,
    BLUEPRINT_GOLANG_CLIENT_PRESERVED,
    BLUEPRINT_GOLANG_CONFORMANCE_PRESERVED,
    BLUEPRINT_GOLANG_SERVER_PRESERVED,
    BLUEPRINT_GOLANG_SUITE_PRESERVED,
    BLUEPRINT_JAVA_CLIENT_PRESERVED,
    BLUEPRINT_JAVA_CONFORMANCE_PRESERVED,
    BLUEPRINT_JAVA_SERVER_PRESERVED,
    BLUEPRINT_JAVA_SUITE_PRESERVED,
    BLUEPRINT_KOTLIN_CLIENT_PRESERVED,
    BLUEPRINT_KOTLIN_CONFORMANCE_PRESERVED,
    BLUEPRINT_KOTLIN_PRESERVED,
    BLUEPRINT_PYTHON_PRESERVED,
    BLUEPRINT_TYPESCRIPT_PRESERVED,
    GRPC_GO_PRESERVED,
    GRPC_PYTHON_PRESERVED,
    WAILS_HELLO_GOLANG_PRESERVED,
    WAILS_HELLO_TYPESCRIPT_PRESERVED,
)
from .models import BlueprintExampleWorkspace, GrpcExampleWorkspace, WailsHelloExampleWorkspace

def _blueprint_workspace(root: Path) -> BlueprintExampleWorkspace:
    return BlueprintExampleWorkspace(
        root=root,
        config_path=root / "api-blueprint.toml",
        golang_dir=root / "golang",
        golang_server_dir=root / "golang" / "server",
        golang_client_dir=root / "golang" / "client",
        golang_suite_dir=root / "golang" / "suite",
        golang_conformance_dir=root / "golang" / "conformance",
        typescript_dir=root / "typescript",
        kotlin_dir=root / "kotlin",
        kotlin_client_dir=root / "kotlin" / "client",
        kotlin_server_dir=root / "kotlin" / "server",
        kotlin_conformance_dir=root / "kotlin" / "conformance",
        java_dir=root / "java",
        java_client_dir=root / "java" / "client",
        java_server_dir=root / "java" / "server",
        java_suite_dir=root / "java" / "suite",
        java_conformance_dir=root / "java" / "conformance",
        python_dir=root / "python",
        flutter_dir=root / "flutter",
        wails_v2_dir=root / "wails-harness" / "v2",
        wails_v3_dir=root / "wails-harness" / "v3",
    )


def _grpc_workspace(root: Path) -> GrpcExampleWorkspace:
    return GrpcExampleWorkspace(
        root=root,
        config_path=root / "api-blueprint.toml",
        protos_dir=root / "grpc" / "protos",
        go_dir=root / "grpc" / "go",
        python_dir=root / "grpc" / "python",
    )


def _wails_hello_workspace(root: Path) -> WailsHelloExampleWorkspace:
    return WailsHelloExampleWorkspace(
        root=root,
        config_path=root / "api-blueprint.toml",
        golang_dir=root / "golang",
        typescript_dir=root / "typescript",
        app_dir=root / "app",
    )


def prepare_blueprint_workspace(repo_root: Path) -> BlueprintExampleWorkspace:
    examples_root = repo_root / "examples"
    workspace_root = Path(tempfile.mkdtemp(prefix="api-blueprint-blueprint-examples-"))
    shutil.copytree(examples_root / "blueprints", workspace_root / "blueprints")
    shutil.copy2(examples_root / "api-blueprint.toml", workspace_root / "api-blueprint.toml")
    if (examples_root / "wails-harness").is_dir():
        shutil.copytree(
            examples_root / "wails-harness",
            workspace_root / "wails-harness",
            ignore=shutil.ignore_patterns("node_modules", "build"),
        )
    _prepare_blueprint_outputs(source_root=examples_root, target_root=workspace_root)
    return _blueprint_workspace(workspace_root)


def prepare_wails_hello_workspace(repo_root: Path) -> WailsHelloExampleWorkspace:
    source_root = repo_root / "examples" / "wails-hello"
    workspace_root = Path(tempfile.mkdtemp(prefix="api-blueprint-wails-hello-"))
    shutil.copytree(
        source_root,
        workspace_root,
        ignore=_ignore_wails_hello_workspace(source_root),
        dirs_exist_ok=True,
    )
    _prepare_wails_hello_outputs(source_root=source_root, target_root=workspace_root)
    return _wails_hello_workspace(workspace_root)


def prepare_grpc_workspace(repo_root: Path) -> GrpcExampleWorkspace:
    examples_root = repo_root / "examples"
    workspace_root = Path(tempfile.mkdtemp(prefix="api-blueprint-grpc-examples-"))
    shutil.copytree(examples_root / "blueprints", workspace_root / "blueprints")
    shutil.copy2(examples_root / "api-blueprint.toml", workspace_root / "api-blueprint.toml")
    _prepare_grpc_outputs(source_root=examples_root / "grpc", target_root=workspace_root / "grpc")
    return _grpc_workspace(workspace_root)


def _prepare_blueprint_outputs(*, source_root: Path, target_root: Path) -> None:
    _prepare_contract_outputs(target_root)
    go_server_preserved = _capture_relative_files(source_root / "golang" / "server", BLUEPRINT_GOLANG_SERVER_PRESERVED)
    go_client_preserved = _capture_relative_files(source_root / "golang" / "client", BLUEPRINT_GOLANG_CLIENT_PRESERVED)
    go_suite_preserved = _capture_relative_files(source_root / "golang" / "suite", BLUEPRINT_GOLANG_SUITE_PRESERVED)
    go_conformance_preserved = _capture_relative_files(
        source_root / "golang" / "conformance",
        BLUEPRINT_GOLANG_CONFORMANCE_PRESERVED,
    )
    shutil.rmtree(target_root / "golang", ignore_errors=True)
    _prepare_output_dir(
        target_root / "golang" / "server",
        go_server_preserved,
    )
    _prepare_output_dir(
        target_root / "golang" / "client",
        go_client_preserved,
    )
    _prepare_output_dir(
        target_root / "golang" / "suite",
        go_suite_preserved,
    )
    _prepare_output_dir(
        target_root / "golang" / "conformance",
        go_conformance_preserved,
    )
    _prepare_output_dir(
        target_root / "typescript",
        _capture_relative_files(source_root / "typescript", BLUEPRINT_TYPESCRIPT_PRESERVED),
    )
    kotlin_conformance_preserved = _capture_relative_files(
        source_root / "kotlin" / "conformance",
        BLUEPRINT_KOTLIN_CONFORMANCE_PRESERVED,
    )
    shutil.rmtree(target_root / "kotlin", ignore_errors=True)
    _prepare_output_dir(
        target_root / "kotlin" / "client",
        _capture_relative_files(
            source_root / "kotlin" / "client",
            (*BLUEPRINT_KOTLIN_PRESERVED, *BLUEPRINT_KOTLIN_CLIENT_PRESERVED),
        ),
    )
    _prepare_output_dir(
        target_root / "kotlin" / "server",
        _capture_relative_files(source_root / "kotlin" / "server", BLUEPRINT_KOTLIN_PRESERVED),
    )
    _prepare_output_dir(
        target_root / "kotlin" / "conformance",
        kotlin_conformance_preserved,
    )
    _prepare_output_dir(
        target_root / "java" / "client",
        _capture_relative_files(source_root / "java" / "client", BLUEPRINT_JAVA_CLIENT_PRESERVED),
    )
    _prepare_output_dir(
        target_root / "java" / "server",
        _capture_relative_files(source_root / "java" / "server", BLUEPRINT_JAVA_SERVER_PRESERVED),
    )
    _prepare_output_dir(
        target_root / "java" / "suite",
        _capture_relative_files(source_root / "java" / "suite", BLUEPRINT_JAVA_SUITE_PRESERVED),
    )
    _prepare_output_dir(
        target_root / "java" / "conformance",
        _capture_relative_files(source_root / "java" / "conformance", BLUEPRINT_JAVA_CONFORMANCE_PRESERVED),
    )
    _prepare_output_dir(
        target_root / "python",
        _capture_relative_files(source_root / "python", BLUEPRINT_PYTHON_PRESERVED),
    )
    _prepare_output_dir(
        target_root / "flutter",
        _capture_relative_files(source_root / "flutter", BLUEPRINT_FLUTTER_PRESERVED),
    )


def _prepare_contract_outputs(target_root: Path) -> None:
    for name in (
        "api-blueprint.index.json",
        "api-blueprint.contract.json",
        "api-blueprint.contract.md",
        "api-blueprint.agent.json",
        "api-blueprint.agent.md",
    ):
        (target_root / name).unlink(missing_ok=True)
    shutil.rmtree(target_root / "api-blueprint.contract.d", ignore_errors=True)


def _prepare_grpc_outputs(*, source_root: Path, target_root: Path) -> None:
    _prepare_output_dir(
        target_root / "protos",
        _capture_relative_files(source_root / "protos", ()),
    )
    _prepare_output_dir(
        target_root / "go",
        _capture_relative_files(source_root / "go", GRPC_GO_PRESERVED),
    )
    _prepare_output_dir(
        target_root / "python",
        _capture_relative_files(source_root / "python", GRPC_PYTHON_PRESERVED),
    )


def _prepare_wails_hello_outputs(*, source_root: Path, target_root: Path) -> None:
    _prepare_output_dir(
        target_root / "golang",
        _capture_relative_files(source_root / "golang", WAILS_HELLO_GOLANG_PRESERVED),
    )
    _prepare_output_dir(
        target_root / "typescript",
        _capture_relative_files(source_root / "typescript", WAILS_HELLO_TYPESCRIPT_PRESERVED),
    )


def _ignore_wails_hello_workspace(source_root: Path) -> Callable[[str, list[str]], set[str]]:
    def ignore(dir_path: str, names: list[str]) -> set[str]:
        current_dir = Path(dir_path)
        try:
            relative_dir = current_dir.relative_to(source_root)
        except ValueError:
            return set()

        ignored: set[str] = set()
        if relative_dir == Path("app") / "frontend":
            ignored.update({"node_modules", "package-lock.json"} & set(names))
        if relative_dir == Path("app") / "frontend" / "dist":
            ignored.update({"assets"} & set(names))
        if relative_dir == Path("app") / "build":
            ignored.update(set(names) - {"config.yml"})
        return ignored

    return ignore


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
