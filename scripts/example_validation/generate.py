from __future__ import annotations

import subprocess
from pathlib import Path

from .constants import PROJECT_ROOT  # Ensures src/ is importable before loading generator.
from .models import BlueprintExampleWorkspace, ExampleValidationTarget, GrpcExampleWorkspace, WailsHelloExampleWorkspace
from .workspace import (
    _blueprint_workspace,
    _grpc_workspace,
    _prepare_blueprint_go_server_output,
    _prepare_blueprint_target_output,
    _prepare_blueprint_outputs,
    _prepare_grpc_outputs,
    _prepare_wails_hello_outputs,
    _wails_hello_workspace,
)
from api_blueprint.application import generator

def regenerate_blueprint_examples(workspace: BlueprintExampleWorkspace) -> None:
    generator.generate(
        workspace.config_path,
        target_ids=(
            "contract",
            "http",
            "http.kotlin",
            "http.python",
            "java.server",
            "java.client",
            "wails.v2",
            "wails.v3",
        ),
    )
    _tidy_go_module(workspace.golang_server_dir)
    _tidy_go_module(workspace.golang_client_dir)


def regenerate_blueprint_go_server_example(workspace: BlueprintExampleWorkspace) -> None:
    generator.generate(workspace.config_path, target_ids=("go.server",))
    _tidy_go_module(workspace.golang_server_dir)


def regenerate_blueprint_target_example(
    workspace: BlueprintExampleWorkspace,
    target: ExampleValidationTarget,
) -> None:
    target_ids = _blueprint_generation_target_ids(target)
    generator.generate(workspace.config_path, target_ids=target_ids)
    _tidy_generated_go_modules(workspace, target)


def regenerate_blueprint_golang_suite_examples(workspace: BlueprintExampleWorkspace) -> None:
    generator.generate(workspace.config_path, target_ids=("go.server", "go.client", "typescript.client", "python.client"))
    _tidy_go_module(workspace.golang_server_dir)
    _tidy_go_module(workspace.golang_client_dir)


def regenerate_blueprint_java_suite_examples(workspace: BlueprintExampleWorkspace) -> None:
    generator.generate(workspace.config_path, target_ids=("java.server", "java.client"))


def regenerate_grpc_examples(workspace: GrpcExampleWorkspace) -> None:
    generator.generate(workspace.config_path, target_ids=("grpc.go", "grpc.python"))
    _tidy_go_module(workspace.go_dir)


def regenerate_wails_hello_example(workspace: WailsHelloExampleWorkspace) -> None:
    generator.generate(workspace.config_path, target_ids=("hello.v3",))
    _tidy_go_module(workspace.golang_dir)
    _tidy_go_module(workspace.app_dir)


def regenerate_repo_blueprint_examples(repo_root: Path) -> None:
    examples_root = repo_root / "examples"
    _prepare_blueprint_outputs(source_root=examples_root, target_root=examples_root)
    regenerate_blueprint_examples(_blueprint_workspace(examples_root))


def regenerate_repo_blueprint_go_server_example(repo_root: Path) -> None:
    examples_root = repo_root / "examples"
    _prepare_blueprint_go_server_output(source_root=examples_root, target_root=examples_root)
    regenerate_blueprint_go_server_example(_blueprint_workspace(examples_root))


def regenerate_repo_blueprint_target_example(repo_root: Path, target: ExampleValidationTarget) -> None:
    examples_root = repo_root / "examples"
    _prepare_blueprint_target_output(source_root=examples_root, target_root=examples_root, target=target)
    regenerate_blueprint_target_example(_blueprint_workspace(examples_root), target)


def regenerate_repo_grpc_examples(repo_root: Path) -> None:
    example_root = repo_root / "examples" / "grpc"
    _prepare_grpc_outputs(source_root=example_root, target_root=example_root)
    regenerate_grpc_examples(_grpc_workspace(repo_root / "examples"))


def regenerate_repo_wails_hello_example(repo_root: Path) -> None:
    example_root = repo_root / "examples" / "wails-hello"
    _prepare_wails_hello_outputs(source_root=example_root, target_root=example_root)
    regenerate_wails_hello_example(_wails_hello_workspace(example_root))

def _tidy_go_module(go_dir: Path) -> None:
    subprocess.run(["go", "mod", "tidy"], cwd=go_dir, check=True)


def _blueprint_generation_target_ids(target: ExampleValidationTarget) -> tuple[str, ...]:
    mapping: dict[ExampleValidationTarget, tuple[str, ...]] = {
        ExampleValidationTarget.GO_SERVER: ("go.server",),
        ExampleValidationTarget.GO_CLIENT: ("go.client",),
        ExampleValidationTarget.TYPESCRIPT_CLIENT: ("typescript.client",),
        ExampleValidationTarget.PYTHON_HTTP: ("http.python",),
        ExampleValidationTarget.KOTLIN_HTTP: ("http.kotlin",),
        ExampleValidationTarget.JAVA_HTTP: ("java.server", "java.client"),
        ExampleValidationTarget.FLUTTER_CLIENT: ("flutter.client",),
        ExampleValidationTarget.SWIFT_CLIENT: ("swift.client",),
        ExampleValidationTarget.WAILS_BLUEPRINT: ("wails.v2", "wails.v3"),
    }
    try:
        return mapping[target]
    except KeyError as exc:
        raise ValueError(f"target {target.value} is not a Blueprint example target") from exc


def _tidy_generated_go_modules(workspace: BlueprintExampleWorkspace, target: ExampleValidationTarget) -> None:
    if target in (ExampleValidationTarget.GO_SERVER, ExampleValidationTarget.WAILS_BLUEPRINT):
        _tidy_go_module(workspace.golang_server_dir)
    if target is ExampleValidationTarget.GO_CLIENT:
        _tidy_go_module(workspace.golang_client_dir)
