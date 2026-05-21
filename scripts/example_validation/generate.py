from __future__ import annotations

import subprocess
from pathlib import Path

from .constants import PROJECT_ROOT  # Ensures src/ is importable before loading generator.
from .models import BlueprintExampleWorkspace, GrpcExampleWorkspace, WailsHelloExampleWorkspace
from .workspace import (
    _blueprint_workspace,
    _grpc_workspace,
    _prepare_blueprint_outputs,
    _prepare_grpc_outputs,
    _prepare_wails_hello_outputs,
    _wails_hello_workspace,
)
from api_blueprint.application import generator

def regenerate_blueprint_examples(workspace: BlueprintExampleWorkspace) -> None:
    generator.generate(
        workspace.config_path,
        target_ids=("contract", "http", "http.kotlin", "http.python", "http.java", "wails.v2", "wails.v3"),
    )
    _tidy_go_module(workspace.golang_server_dir)
    _tidy_go_module(workspace.golang_client_dir)


def regenerate_blueprint_golang_suite_examples(workspace: BlueprintExampleWorkspace) -> None:
    generator.generate(workspace.config_path, target_ids=("go.server", "go.client", "typescript.client", "python.client"))
    _tidy_go_module(workspace.golang_server_dir)
    _tidy_go_module(workspace.golang_client_dir)


def regenerate_blueprint_java_suite_examples(workspace: BlueprintExampleWorkspace) -> None:
    generator.generate(workspace.config_path, target_ids=("http.java",))


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
