from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .constants import WAILS_V2_BIN_ENV, WAILS_V3_BIN_ENV
from .language_checks import (
    _validate_flutter_sources,
    _validate_java_sources,
    _validate_kotlin_sources,
    _validate_python_sources,
    _validate_swift_sources,
)
from .models import BlueprintExampleWorkspace, ExampleValidationError, GrpcExampleWorkspace, WailsHelloExampleWorkspace
from .connection_contract import _validate_blueprint_connection_examples
from .tools import resolve_wails_bin

def compile_generated_examples(workspace: BlueprintExampleWorkspace) -> None:
    _validate_blueprint_connection_examples(workspace)
    subprocess.run(["tsc", "-p", str(workspace.typescript_dir / "tsconfig.json"), "--noEmit"], check=True)
    subprocess.run(["go", "test", "./..."], cwd=workspace.golang_server_dir, check=True)
    subprocess.run(["go", "test", "./..."], cwd=workspace.golang_client_dir, check=True)
    _validate_kotlin_sources(workspace.kotlin_dir)
    _validate_java_sources(workspace.java_dir)
    _validate_python_sources(workspace.python_dir)
    _validate_flutter_sources(workspace.flutter_dir)
    _validate_swift_sources(workspace.swift_dir)
    _compile_wails_harness(workspace.wails_v2_dir, version="v2")
    _compile_wails_harness(workspace.wails_v3_dir, version="v3")


def compile_generated_grpc_examples(workspace: GrpcExampleWorkspace) -> None:
    proto_files = sorted(path.relative_to(workspace.protos_dir).as_posix() for path in workspace.protos_dir.rglob("*.proto"))
    if not proto_files:
        raise ExampleValidationError(f"missing generated proto files under {workspace.protos_dir}")
    with tempfile.NamedTemporaryFile(suffix=".pb") as descriptor:
        subprocess.run(
            [
                "protoc",
                f"--proto_path={workspace.protos_dir}",
                f"--descriptor_set_out={descriptor.name}",
                *proto_files,
            ],
            cwd=workspace.protos_dir,
            check=True,
        )
    subprocess.run(["go", "test", "./..."], cwd=workspace.go_dir, check=True)
    _compile_python_grpc_examples(workspace.python_dir)


def _compile_python_grpc_examples(python_dir: Path) -> None:
    snippets = (
        "import pb.api.api_pb2",
        "import pb.api.api_pb2_grpc",
        "import pb.api.demo_pb2",
        "import pb.api.demo_pb2_grpc",
        "import pb.api.hello_pb2",
        "import pb.api.hello_pb2_grpc",
        "import pb.static.static_pb2",
        "import pb.static.static_pb2_grpc",
    )
    subprocess.run(
        [sys.executable, "-B", "-c", "; ".join(snippets)],
        cwd=python_dir,
        check=True,
    )


def compile_wails_hello_example(workspace: WailsHelloExampleWorkspace) -> None:
    subprocess.run(["tsc", "-p", str(workspace.typescript_dir / "tsconfig.json"), "--noEmit"], check=True)
    subprocess.run(["go", "test", "./..."], cwd=workspace.golang_dir, check=True)
    subprocess.run(["go", "test", "./..."], cwd=workspace.app_dir, check=True)
    _assert_wails_hello_has_no_http_adapter_deps(workspace.app_dir)
    _compile_wails_harness(workspace.app_dir, version="v3")


def compile_repo_examples(repo_root: Path) -> None:
    workspace = _blueprint_workspace(repo_root / "examples")
    subprocess.run(["tsc", "-p", str(workspace.typescript_dir / "tsconfig.json"), "--noEmit"], check=True)
    subprocess.run(["go", "test", "./..."], cwd=workspace.golang_server_dir, check=True)
    subprocess.run(["go", "test", "./..."], cwd=workspace.golang_client_dir, check=True)
    _validate_kotlin_sources(workspace.kotlin_dir)
    _validate_java_sources(workspace.java_dir)
    _validate_python_sources(workspace.python_dir)
    _validate_flutter_sources(workspace.flutter_dir)
    _validate_swift_sources(workspace.swift_dir)


def compile_repo_grpc_examples(repo_root: Path) -> None:
    compile_generated_grpc_examples(_grpc_workspace(repo_root / "examples"))

def _assert_wails_hello_has_no_http_adapter_deps(app_dir: Path) -> None:
    result = subprocess.run(
        ["go", "list", "-deps", "./..."],
        cwd=app_dir,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    forbidden = ("github.com/gin-gonic/gin", "github.com/coder/websocket")
    found = [dep for dep in forbidden if dep in result.stdout.splitlines()]
    if found:
        raise ExampleValidationError(
            "wails-hello app unexpectedly depends on HTTP adapter packages:\n" + "\n".join(found)
        )


def _compile_wails_harness(harness_dir: Path, *, version: str) -> None:
    if not harness_dir.is_dir():
        raise ExampleValidationError(f"missing Wails harness example: {harness_dir}")

    env_var = WAILS_V2_BIN_ENV if version == "v2" else WAILS_V3_BIN_ENV
    default_binary = "wails" if version == "v2" else "wails3"
    wails_bin = resolve_wails_bin(env_var, default_binary)
    if wails_bin is None:
        raise ExampleValidationError(
            f"missing Wails {version} CLI requirement: install `{default_binary}` or set `{env_var}`."
        )

    subprocess.run([wails_bin, "doctor"], cwd=harness_dir, check=True)
    subprocess.run([wails_bin, "build"], cwd=harness_dir, check=True)
