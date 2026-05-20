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
from typing import Callable, Iterable, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from api_blueprint.application import generator

GO_ENUM_VERSION = "v0.9.2"
KOTLIN_VERSION = "2.1.21"
KOTLINX_COROUTINES_VERSION = "1.10.2"
KOTLINX_SERIALIZATION_JSON_VERSION = "1.8.1"
OKHTTP_VERSION = "4.12.0"
OKIO_VERSION = "3.9.1"
KTOR_VERSION = "3.1.3"
JACKSON_DATABIND_VERSION = "2.17.2"
SPRING_BOOT_VERSION = "3.3.6"
GRADLE_BIN_ENV = "API_BLUEPRINT_GRADLE_BIN"
WAILS_V2_BIN_ENV = "API_BLUEPRINT_WAILS_V2_BIN"
WAILS_V3_BIN_ENV = "API_BLUEPRINT_WAILS_V3_BIN"

BLUEPRINT_GOLANG_SERVER_PRESERVED = (
    "go.mod",
    "go.sum",
    "main.go",
    "views/routes/api/binary/impl.go",
    "views/routes/api/demo/assistant_session_error.go",
    "views/routes/api/demo/assistant_session_processor.go",
    "views/routes/api/demo/assistant_session_session.go",
    "views/routes/api/demo/impl.go",
    "views/routes/api/hello/impl.go",
)
BLUEPRINT_GOLANG_CLIENT_PRESERVED = (
    "go.mod",
    "go.sum",
)
BLUEPRINT_GOLANG_SUITE_PRESERVED = (
    "go.mod",
    "main.go",
)
BLUEPRINT_TYPESCRIPT_PRESERVED = (
    ".vscode/settings.json",
    "index.ts",
    "suite.ts",
    "tsconfig.json",
)
BLUEPRINT_KOTLIN_PRESERVED = ()
BLUEPRINT_JAVA_CLIENT_PRESERVED = (
    "com/example/apiblueprint/api/runtime/ApiClient.java",
    "com/example/apiblueprint/api/transports/http/HttpApiClient.java",
    "com/example/apiblueprint/api/routes/api/ApiApi.java",
    "com/example/apiblueprint/api/routes/api/binary/BinaryApi.java",
    "com/example/apiblueprint/api/routes/api/demo/DemoApi.java",
    "com/example/apiblueprint/api/routes/api/hello/HelloApi.java",
    "com/example/apiblueprint/static_/runtime/ApiClient.java",
    "com/example/apiblueprint/static_/transports/http/HttpApiClient.java",
    "com/example/apiblueprint/static_/routes/static_/StaticApi.java",
)
BLUEPRINT_JAVA_SERVER_PRESERVED = (
    "com/example/apiblueprint/api/routes/api/ApiService.java",
    "com/example/apiblueprint/api/routes/api/binary/BinaryService.java",
    "com/example/apiblueprint/api/routes/api/demo/DemoService.java",
    "com/example/apiblueprint/api/routes/api/hello/HelloService.java",
    "com/example/apiblueprint/static_/routes/static_/StaticService.java",
)
BLUEPRINT_JAVA_SUITE_PRESERVED = (
    ".gitignore",
    "build.gradle.kts",
    "settings.gradle.kts",
    "src/main/java/com/example/apiblueprint/suite/JavaExampleSuite.java",
)
BLUEPRINT_PYTHON_PRESERVED = ("client/suite.py",)
BLUEPRINT_FLUTTER_PRESERVED = (
    "pubspec.yaml",
    "analysis_options.yaml",
    "lib/src/api/runtime/api_client.dart",
    "lib/src/api/runtime/api_json_codecs.dart",
    "lib/src/api/transports/http/http_api_client.dart",
    "lib/src/api/routes/api/api_api.dart",
    "lib/src/api/routes/api/api_types.dart",
    "lib/src/api/routes/api/binary/binary.dart",
    "lib/src/api/routes/api/binary/binary_api.dart",
    "lib/src/api/routes/api/binary/binary_types.dart",
    "lib/src/api/routes/api/demo/demo_api.dart",
    "lib/src/api/routes/api/demo/demo_types.dart",
    "lib/src/api/routes/api/hello/hello_api.dart",
    "lib/src/api/routes/api/hello/hello_types.dart",
    "test/api_contract_test.dart",
    "test/binary_contract_test.dart",
    "test/http_transport_test.dart",
)
WAILS_HELLO_GOLANG_PRESERVED = (
    "go.mod",
    "go.sum",
    "routes/api/hello/impl.go",
)
WAILS_HELLO_TYPESCRIPT_PRESERVED = ("tsconfig.json",)
GRPC_GO_PRESERVED = ("go.mod", "go.sum")
GRPC_PYTHON_PRESERVED = ()
EXAMPLE_SNAPSHOT_IGNORES: Mapping[str, frozenset[str]] = {
    "blueprint/java/suite": frozenset((".gradle", "bin", "build")),
    "blueprint/flutter": frozenset((".dart_tool", "pubspec.lock")),
}


class ExampleValidationError(RuntimeError):
    pass


class ExampleValidationMode(StrEnum):
    CHECK = "check"
    COMPILE = "compile"
    REFRESH = "refresh"
    GOLANG_SUITE = "golang-suite"
    JAVA_SUITE = "java-suite"


class ExampleValidationScope(StrEnum):
    ALL = "all"
    BLUEPRINT = "blueprint"
    GRPC = "grpc"
    WAILS_HELLO = "wails-hello"


@dataclass(frozen=True)
class BlueprintExampleWorkspace:
    root: Path
    config_path: Path
    golang_dir: Path
    golang_server_dir: Path
    golang_client_dir: Path
    golang_suite_dir: Path
    typescript_dir: Path
    kotlin_dir: Path
    kotlin_client_dir: Path
    kotlin_server_dir: Path
    java_dir: Path
    java_client_dir: Path
    java_server_dir: Path
    java_suite_dir: Path
    python_dir: Path
    flutter_dir: Path
    wails_v2_dir: Path
    wails_v3_dir: Path


@dataclass(frozen=True)
class GrpcExampleWorkspace:
    root: Path
    config_path: Path
    protos_dir: Path
    go_dir: Path
    python_dir: Path


@dataclass(frozen=True)
class WailsHelloExampleWorkspace:
    root: Path
    config_path: Path
    golang_dir: Path
    typescript_dir: Path
    app_dir: Path


def resolve_gradle_bin() -> str | None:
    configured = os.environ.get(GRADLE_BIN_ENV)
    if configured:
        configured_path = Path(configured).expanduser()
        if configured_path.is_file():
            return str(configured_path)
        resolved = shutil.which(configured)
        if resolved is not None:
            return resolved
    return shutil.which("gradle")


def resolve_wails_bin(env_var: str, default_binary: str) -> str | None:
    configured = os.environ.get(env_var)
    if configured:
        configured_path = Path(configured).expanduser()
        if configured_path.is_file():
            return str(configured_path)
        resolved = shutil.which(configured)
        if resolved is not None:
            return resolved
    return shutil.which(default_binary)


def collect_missing_validation_requirements(scope: ExampleValidationScope = ExampleValidationScope.ALL) -> tuple[str, ...]:
    requirements_by_scope: dict[ExampleValidationScope, tuple[tuple[str, str], ...]] = {
        ExampleValidationScope.ALL: (
            (
                "tsc",
                "install the TypeScript CLI, for example `npm install --global typescript`.",
            ),
            (
                "npm",
                "install Node.js/npm and ensure `npm` is available on PATH.",
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
                "dart",
                "install the Dart SDK and ensure `dart` is available on PATH.",
            ),
            (
                "protoc",
                "install the Protocol Buffers compiler, for example `brew install protobuf` or `apt-get install protobuf-compiler`.",
            ),
        ),
        ExampleValidationScope.BLUEPRINT: (
            (
                "tsc",
                "install the TypeScript CLI, for example `npm install --global typescript`.",
            ),
            (
                "npm",
                "install Node.js/npm and ensure `npm` is available on PATH.",
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
                "dart",
                "install the Dart SDK and ensure `dart` is available on PATH.",
            ),
        ),
        ExampleValidationScope.GRPC: (
            (
                "protoc",
                "install the Protocol Buffers compiler, for example `brew install protobuf` or `apt-get install protobuf-compiler`.",
            ),
            (
                "protoc-gen-go",
                "install it with `go install google.golang.org/protobuf/cmd/protoc-gen-go@latest`.",
            ),
            (
                "protoc-gen-go-grpc",
                "install it with `go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest`.",
            ),
            (
                "go",
                "install Go and ensure `go` is available on PATH.",
            ),
        ),
        ExampleValidationScope.WAILS_HELLO: (
            (
                "tsc",
                "install the TypeScript CLI, for example `npm install --global typescript`.",
            ),
            (
                "npm",
                "install Node.js/npm and ensure `npm` is available on PATH.",
            ),
            (
                "go",
                "install Go and ensure `go` is available on PATH.",
            ),
        ),
    }

    missing: list[str] = []
    for name, guidance in requirements_by_scope[scope]:
        if shutil.which(name) is None:
            missing.append(f"{name}: {guidance}")

    if scope in (ExampleValidationScope.ALL, ExampleValidationScope.BLUEPRINT) and resolve_gradle_bin() is None:
        missing.append(
            "gradle: install Gradle and ensure `gradle` is available on PATH, "
            f"or set `{GRADLE_BIN_ENV}` to an executable Gradle binary."
        )
    if scope in (ExampleValidationScope.ALL, ExampleValidationScope.BLUEPRINT) and resolve_wails_bin(
        WAILS_V2_BIN_ENV, "wails"
    ) is None:
        missing.append(
            "wails: install the Wails v2 CLI and ensure `wails` is available on PATH, "
            f"or set `{WAILS_V2_BIN_ENV}` to the executable."
        )
    if scope in (
        ExampleValidationScope.ALL,
        ExampleValidationScope.BLUEPRINT,
        ExampleValidationScope.WAILS_HELLO,
    ) and resolve_wails_bin(WAILS_V3_BIN_ENV, "wails3") is None:
        missing.append(
            "wails3: install the Wails v3 CLI and ensure `wails3` is available on PATH, "
            f"or set `{WAILS_V3_BIN_ENV}` to the executable."
        )
    if scope in (ExampleValidationScope.ALL, ExampleValidationScope.GRPC) and importlib.util.find_spec(
        "grpc_tools"
    ) is None:
        missing.append(
            "grpcio-tools: install Python gRPC tooling with `uv add --dev grpcio-tools` "
            "or `pip install grpcio-tools`."
        )

    return tuple(missing)


def ensure_validation_requirements(scope: ExampleValidationScope = ExampleValidationScope.ALL) -> None:
    missing = collect_missing_validation_requirements(scope)
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
        golang_server_dir=root / "golang" / "server",
        golang_client_dir=root / "golang" / "client",
        golang_suite_dir=root / "golang" / "suite",
        typescript_dir=root / "typescript",
        kotlin_dir=root / "kotlin",
        kotlin_client_dir=root / "kotlin" / "client",
        kotlin_server_dir=root / "kotlin" / "server",
        java_dir=root / "java",
        java_client_dir=root / "java" / "client",
        java_server_dir=root / "java" / "server",
        java_suite_dir=root / "java" / "suite",
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
        target_root / "typescript",
        _capture_relative_files(source_root / "typescript", BLUEPRINT_TYPESCRIPT_PRESERVED),
    )
    shutil.rmtree(target_root / "kotlin", ignore_errors=True)
    _prepare_output_dir(
        target_root / "kotlin" / "client",
        _capture_relative_files(source_root / "kotlin" / "client", BLUEPRINT_KOTLIN_PRESERVED),
    )
    _prepare_output_dir(
        target_root / "kotlin" / "server",
        _capture_relative_files(source_root / "kotlin" / "server", BLUEPRINT_KOTLIN_PRESERVED),
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
        )
    )
    _validate_blueprint_connection_examples(workspace)


def _validate_blueprint_connection_examples(workspace: BlueprintExampleWorkspace) -> None:
    files = {
        "go_route_interface": workspace.golang_server_dir / "views" / "routes" / "api" / "demo" / "gen_interface.go",
        "go_route_gen_impl": workspace.golang_server_dir / "views" / "routes" / "api" / "demo" / "gen_impl.go",
        "go_route_types": workspace.golang_server_dir / "views" / "routes" / "api" / "demo" / "gen_types.go",
        "go_route_messages": workspace.golang_server_dir
        / "views"
        / "routes"
        / "api"
        / "demo"
        / "gen_messages.go",
        "go_route_message_cases": workspace.golang_server_dir
        / "views"
        / "routes"
        / "api"
        / "demo"
        / "gen_message_cases.go",
        "go_route_impl": workspace.golang_server_dir / "views" / "routes" / "api" / "demo" / "impl.go",
        "go_route_assistant_session": workspace.golang_server_dir
        / "views"
        / "routes"
        / "api"
        / "demo"
        / "assistant_session_session.go",
        "go_route_assistant_processor": workspace.golang_server_dir
        / "views"
        / "routes"
        / "api"
        / "demo"
        / "assistant_session_processor.go",
        "go_route_assistant_error": workspace.golang_server_dir
        / "views"
        / "routes"
        / "api"
        / "demo"
        / "assistant_session_error.go",
        "go_http_adapter": workspace.golang_server_dir / "views" / "transports" / "http" / "api" / "demo" / "gen_interface.go",
        "go_client_route": workspace.golang_client_dir / "routes" / "api" / "demo" / "gen_client.go",
        "go_client_messages": workspace.golang_client_dir / "routes" / "api" / "demo" / "gen_messages.go",
        "go_client_message_cases": workspace.golang_client_dir / "routes" / "api" / "demo" / "gen_message_cases.go",
        "go_client_http": workspace.golang_client_dir / "transports" / "http" / "gen_transport.go",
        "go_error_lookup": workspace.golang_client_dir / "runtime" / "gen_error_lookup.go",
        "go_wails_v3_service": workspace.golang_server_dir
        / "views"
        / "transports"
        / "wailsv3"
        / "api"
        / "demo"
        / "gen_service.go",
        "ts_wails_v3_transport": workspace.typescript_dir
        / "api"
        / "transports"
        / "wailsv3"
        / "gen_transport.ts",
        "ts_wails_v3_runtime": workspace.typescript_dir
        / "api"
        / "transports"
        / "wailsv3"
        / "gen_runtime.ts",
        "ts_wails_v3_bindings": workspace.typescript_dir
        / "api"
        / "transports"
        / "wailsv3"
        / "gen_bindings.ts",
        "index": workspace.root / "api-blueprint.index.json",
        "ts_suite": workspace.typescript_dir / "suite.ts",
        "ts_route_client": workspace.typescript_dir / "api" / "routes" / "api" / "demo" / "gen_client.ts",
        "ts_route_types": workspace.typescript_dir / "api" / "routes" / "api" / "demo" / "gen_types.ts",
        "ts_error_lookup": workspace.typescript_dir / "api" / "runtime" / "gen_error_lookup.ts",
        "python_binary_route": workspace.python_dir
        / "client"
        / "api_blueprint_example_client"
        / "api"
        / "routes"
        / "api"
        / "binary"
        / "gen_types.py",
        "python_error_lookup": workspace.python_dir
        / "client"
        / "api_blueprint_example_client"
        / "api"
        / "runtime"
        / "gen_error_lookup.py",
        "python_client_demo_types": workspace.python_dir
        / "client"
        / "api_blueprint_example_client"
        / "api"
        / "routes"
        / "api"
        / "demo"
        / "gen_types.py",
        "python_server_demo_types": workspace.python_dir
        / "server"
        / "api_blueprint_example_server"
        / "api"
        / "routes"
        / "api"
        / "demo"
        / "gen_types.py",
        "kotlin_client_api_json": workspace.kotlin_client_dir
        / "com"
        / "example"
        / "apiblueprint"
        / "api"
        / "runtime"
        / "ApiJson.kt",
        "kotlin_client_route": workspace.kotlin_client_dir
        / "com"
        / "example"
        / "apiblueprint"
        / "api"
        / "routes"
        / "api"
        / "demo"
        / "GenDemoApi.kt",
        "kotlin_client_demo_types": workspace.kotlin_client_dir
        / "com"
        / "example"
        / "apiblueprint"
        / "api"
        / "routes"
        / "api"
        / "demo"
        / "DemoTypes.kt",
        "kotlin_server_demo_types": workspace.kotlin_server_dir
        / "com"
        / "example"
        / "apiblueprint"
        / "api"
        / "routes"
        / "api"
        / "demo"
        / "DemoTypes.kt",
        "kotlin_server_service": workspace.kotlin_server_dir
        / "com"
        / "example"
        / "apiblueprint"
        / "api"
        / "routes"
        / "api"
        / "demo"
        / "GenDemoService.kt",
        "kotlin_server_ktor": workspace.kotlin_server_dir
        / "com"
        / "example"
        / "apiblueprint"
        / "api"
        / "transports"
        / "ktor"
        / "api"
        / "demo"
        / "GenDemoKtorRoutes.kt",
        "java_client_demo_types": workspace.java_client_dir
        / "com"
        / "example"
        / "apiblueprint"
        / "api"
        / "routes"
        / "api"
        / "demo"
        / "DemoTypes.java",
        "java_client_route": workspace.java_client_dir
        / "com"
        / "example"
        / "apiblueprint"
        / "api"
        / "routes"
        / "api"
        / "demo"
        / "GenDemoApi.java",
        "java_client_api_json": workspace.java_client_dir
        / "com"
        / "example"
        / "apiblueprint"
        / "api"
        / "runtime"
        / "ApiJson.java",
        "java_server_demo_types": workspace.java_server_dir
        / "com"
        / "example"
        / "apiblueprint"
        / "api"
        / "routes"
        / "api"
        / "demo"
        / "DemoTypes.java",
        "flutter_runtime_client": workspace.flutter_dir / "lib" / "src" / "api" / "runtime" / "gen_api_client.dart",
        "flutter_runtime_errors": workspace.flutter_dir
        / "lib"
        / "src"
        / "api"
        / "runtime"
        / "gen_api_error_lookup.dart",
        "flutter_demo_api": workspace.flutter_dir
        / "lib"
        / "src"
        / "api"
        / "routes"
        / "api"
        / "demo"
        / "gen_demo_api.dart",
        "flutter_demo_types": workspace.flutter_dir
        / "lib"
        / "src"
        / "api"
        / "routes"
        / "api"
        / "demo"
        / "gen_demo_types.dart",
        "flutter_binary": workspace.flutter_dir
        / "lib"
        / "src"
        / "api"
        / "routes"
        / "api"
        / "binary"
        / "gen_binary.dart",
        "flutter_http_transport": workspace.flutter_dir
        / "lib"
        / "src"
        / "api"
        / "transports"
        / "http"
        / "gen_http_api_transport.dart",
    }
    missing_files = [label for label, path in files.items() if not path.is_file()]
    if missing_files:
        raise ExampleValidationError("blueprint connection example missing generated files:\n" + "\n".join(missing_files))

    checks = {
        "go stream handler": (
            files["go_route_interface"],
            "SweepEvents(\n"
            "\t\tctx *CTX_SweepEvents,\n"
            "\t\tstream STREAM_SweepEvents,\n"
            "\t) error",
        ),
        "go channel handler": (
            files["go_route_interface"],
            "AssistantSession(\n"
            "\t\tctx *CTX_AssistantSession,\n"
            "\t\tchannel CHANNEL_AssistantSession,\n"
            "\t) error",
        ),
        "go stream message constructor example": (
            files["go_route_impl"],
            "message, err := NewSweepStreamMessageState(&SweepStreamMessage_State_DATA{",
        ),
        "go stream context send example": (files["go_route_impl"], "if err := stream.Send(ctx, message); err != nil {"),
        "go stream context close example": (
            files["go_route_impl"],
            'return stream.Close(ctx, &CLOSE_SweepEvents{Code: 1000, Reason: "example stream complete"})',
        ),
        "go channel scaffold route": (
            files["go_route_assistant_session"],
            "session := newAssistantSessionRouteSession(impl, ctx, channel, &assistantSessionMessageProcessor{})",
        ),
        "go channel scaffold serve loop": (
            files["go_route_assistant_session"],
            "message, err := session.channel.Recv(session.Context())",
        ),
        "go channel scaffold visitor": (
            files["go_route_assistant_session"],
            "if err := VisitAssistantClientMessage(session.messageScope(), message, session.processor); err != nil {",
        ),
        "go channel scaffold scope channel": (
            files["go_route_assistant_session"],
            "Channel CHANNEL_AssistantSession",
        ),
        "go channel processor example": (
            files["go_route_assistant_processor"],
            "type assistantSessionMessageProcessor struct{}",
        ),
        "go channel processor contract": (
            files["go_route_assistant_processor"],
            "var _ AssistantClientMessageProcessor[assistantSessionMessageScope] = (*assistantSessionMessageProcessor)(nil)",
        ),
        "go channel processor input": (
            files["go_route_assistant_processor"],
            "func (processor *assistantSessionMessageProcessor) OnInput(",
        ),
        "go channel processor cancel": (
            files["go_route_assistant_processor"],
            "func (processor *assistantSessionMessageProcessor) OnCancel(",
        ),
        "go channel processor constructor": (
            files["go_route_assistant_processor"],
            "message, err := NewAssistantServerMessageDelta(&AssistantServerMessage_Delta_DATA{",
        ),
        "go channel processor context send": (
            files["go_route_assistant_processor"],
            "return scope.Channel.Send(scope.Context, message)",
        ),
        "go channel processor context close": (
            files["go_route_assistant_processor"],
            "return scope.Channel.Close(scope.Context, &CLOSE_AssistantSession{Code: 1000, Reason: reason})",
        ),
        "go channel error scaffold": (
            files["go_route_assistant_error"],
            "func (session *assistantSessionRouteSession) handleMessageError(",
        ),
        "go channel error typed helper": (
            files["go_route_assistant_error"],
            "IsAssistantClientMessageErrorKind(err, AssistantClientMessageErrorNilProcessor)",
        ),
        "go channel error message type helper": (
            files["go_route_assistant_error"],
            "messageErr.MessageType()",
        ),
        "go generated channel processor": (
            files["go_route_message_cases"],
            "type AssistantClientMessageProcessor[C any] interface {",
        ),
        "go generated channel visitor": (files["go_route_message_cases"], "func VisitAssistantClientMessage[C any]("),
        "go generated channel case": (files["go_route_message_cases"], "type AssistantClientMessageInputCase struct {"),
        "go generated channel decode error": (files["go_route_message_cases"], "AssistantClientMessageErrorDecodeFailed"),
        "go generated channel handler error": (files["go_route_message_cases"], "AssistantClientMessageErrorHandlerFailed"),
        "go generated channel error helper": (
            files["go_route_message_cases"],
            "func IsAssistantClientMessageErrorKind(err error, kinds ...AssistantClientMessageErrorKind) bool",
        ),
        "go generated connection messages": (files["go_route_messages"], "type AssistantClientMessage struct {"),
        "go generated message constructor": (files["go_route_messages"], "func NewAssistantClientMessageCancel("),
        "go typed error return example": (files["go_route_impl"], "return nil, demo_err.RATE_LIMITED.WithToast("),
        "go typed error dynamic toast": (files["go_route_impl"], 'Text:    "请等待 30 秒后重试",'),
        "go unknown typed error example": (
            files["go_route_impl"],
            'return nil, apperrors.New(70001, "example undefined business error")',
        ),
        "go error demo client": (files["go_client_route"], "ErrorDemo("),
        "go error demo route lookup": (
            files["go_error_lookup"],
            'DemoErrRateLimited:   ApiErrorsByID["DemoErr.RATE_LIMITED"],',
        ),
        "go error demo constant": (files["go_error_lookup"], "DemoErrRateLimited   ApiErrorCode = 42901"),
        "go client unsupported connection": (files["go_client_http"], "UnsupportedConnectionError"),
        "go client generated connection messages": (
            files["go_client_messages"],
            "func NewAssistantClientMessageCancel(data *AssistantClientMessage_Cancel_DATA)",
        ),
        "go client generated stream visitor": (
            files["go_client_message_cases"],
            "func VisitSweepStreamMessage[C any](",
        ),
        "go client generated channel visitor": (
            files["go_client_message_cases"],
            "func VisitAssistantServerMessage[C any](",
        ),
        "http stream adapter": (files["go_http_adapter"], "httptransport.STREAM("),
        "http channel adapter": (files["go_http_adapter"], "httptransport.CHANNEL("),
        "wails stream event base": (
            files["go_wails_v3_service"],
            'RouteID:            "api.demo.stream.sweepevents"',
        ),
        "wails channel event base": (
            files["go_wails_v3_service"],
            'RouteID:            "api.demo.channel.assistantsession"',
        ),
        "typescript stream client": (files["ts_route_client"], "subscribeSweepEvents("),
        "typescript channel client": (files["ts_route_client"], "openAssistantSession("),
        "typescript error demo client": (files["ts_route_client"], "errorDemo("),
        "typescript error demo constant": (files["ts_error_lookup"], "export const DemoErr = {"),
        "typescript error demo route lookup": (
            files["ts_error_lookup"],
            '"42901": ApiErrorsByID["DemoErr.RATE_LIMITED"],',
        ),
        "typescript stream union": (
            files["ts_route_types"],
            "export type SweepStreamMessage =\n"
            '  | { type: "state"; data: SweepState }\n'
            '  | { type: "progress"; data: SweepProgress }\n'
            '  | { type: "log"; data: SweepLog };',
        ),
        "typescript channel union": (
            files["ts_route_types"],
            "export type AssistantClientMessage =\n"
            '  | { type: "input"; data: AssistantInput }\n'
            '  | { type: "cancel"; data: AssistantCancel };',
        ),
        "typescript channel variants helper": (files["ts_route_types"], "export const AssistantClientMessageVariants = {"),
        "typescript server dispatcher helper": (files["ts_route_types"], "export function dispatchAssistantServerMessage<R>("),
        "typescript suite client message helper": (files["ts_suite"], "AssistantClientMessageVariants.cancel({ reason: \"suite\" })"),
        "typescript suite server dispatcher helper": (files["ts_suite"], "dispatchAssistantServerMessage(serverMessage, {"),
        "wails v3 bindings import": (
            files["ts_wails_v3_runtime"],
            'import { WAILS_V3_BINDINGS } from "./gen_bindings";',
        ),
        "wails v3 bindings manifest": (
            files["ts_wails_v3_bindings"],
            '"demo.DemoService.OpenAssistantSession": "example.com/project/golang/server/views/transports/wailsv3/api/demo.DemoService.OpenAssistantSession",',
        ),
        "index error demo route": (files["index"], '"id": "api.demo.get.errordemo"'),
        "index error demo url": (files["index"], '"url": "/api/demo/error-demo"'),
        "python binary public types export": (files["python_binary_route"], "from .gen_binary import *"),
        "python error demo constant": (files["python_error_lookup"], "class DemoErr:"),
        "python error demo route lookup": (files["python_error_lookup"], '42901: API_ERRORS_BY_ID["DemoErr.RATE_LIMITED"],'),
        "python client message variants": (
            files["python_client_demo_types"],
            "class AssistantClientMessageVariants:",
        ),
        "python client server dispatcher": (
            files["python_client_demo_types"],
            "def dispatch_assistant_server_message(",
        ),
        "python server client dispatcher": (
            files["python_server_demo_types"],
            "def dispatch_assistant_client_message(",
        ),
        "python typed dispatch error": (
            files["python_client_demo_types"],
            "class AssistantServerMessageDispatchError(Exception):",
        ),
        "kotlin client api json helper": (files["kotlin_client_api_json"], "public val ApiJson: Json = Json"),
        "kotlin channel bridge message types": (
            files["kotlin_client_route"],
            "ApiChannelBridge<AssistantServerMessage, AssistantClientMessage, ConnectionClose>",
        ),
        "kotlin client message variants": (
            files["kotlin_client_demo_types"],
            "public object AssistantClientMessageVariants",
        ),
        "kotlin client server dispatcher": (
            files["kotlin_client_demo_types"],
            "public fun <R> dispatchAssistantServerMessage(",
        ),
        "kotlin server service": (files["kotlin_server_service"], "public interface GenDemoService"),
        "kotlin server client dispatcher": (
            files["kotlin_server_demo_types"],
            "public fun <R> dispatchAssistantClientMessage(",
        ),
        "kotlin server connection unsupported": (
            files["kotlin_server_ktor"],
            '"channel route is not implemented by the generated Ktor adapter"',
        ),
        "java api json helper": (files["java_client_api_json"], "public static final ObjectMapper MAPPER"),
        "java client message variants": (
            files["java_client_demo_types"],
            "public static final class AssistantClientMessageVariants",
        ),
        "java client server dispatcher": (
            files["java_client_demo_types"],
            "public static <R> R dispatchAssistantServerMessage(",
        ),
        "java client channel bridge message types": (
            files["java_client_route"],
            "ApiChannelBridge<DemoTypes.AssistantServerMessage, DemoTypes.AssistantClientMessage, Object>",
        ),
        "java server client dispatcher": (
            files["java_server_demo_types"],
            "public static <R> R dispatchAssistantClientMessage(",
        ),
        "flutter runtime client route": (files["flutter_runtime_client"], "final demo = DemoApi(transport);"),
        "flutter error demo constant": (files["flutter_runtime_errors"], "const rateLimited = 42901;"),
        "flutter stream client": (files["flutter_demo_api"], "subscribeSweepEvents("),
        "flutter channel client": (files["flutter_demo_api"], "openAssistantSession("),
        "flutter channel bridge message types": (
            files["flutter_demo_api"],
            "ApiChannelBridge<AssistantServerMessage, AssistantClientMessage, ConnectionClose>",
        ),
        "flutter client message variants": (files["flutter_demo_types"], "class AssistantClientMessageVariants"),
        "flutter server dispatcher": (files["flutter_demo_types"], "R dispatchAssistantServerMessage<R>("),
        "flutter binary encode": (files["flutter_binary"], "Uint8List encodeDemoPacket(DemoPacket value)"),
        "flutter binary decode": (files["flutter_binary"], "DemoPacket decodeDemoPacket(Uint8List bytes)"),
        "flutter http transport": (files["flutter_http_transport"], "class HttpApiTransport implements ApiTransport"),
        "flutter websocket channel": (files["flutter_http_transport"], "WebSocketChannel.connect"),
    }
    validation_errors = []
    for label, (path, snippet) in checks.items():
        if snippet not in path.read_text(encoding="utf-8"):
            validation_errors.append(label)
    forbidden_checks = {
        "http stream explicit type args": (files["go_http_adapter"], "httptransport.STREAM["),
        "http channel explicit type args": (files["go_http_adapter"], "httptransport.CHANNEL["),
        "wails envelope explicit type args": (files["go_wails_v3_service"], "wailstransport.EnvelopeToReq["),
        "wails response envelope explicit type args": (
            files["go_wails_v3_service"],
            "WrapRSP_JSON_CodeMessageDataEnvelope[",
        ),
        "inline wails v3 bindings manifest": (files["ts_wails_v3_transport"], "const WAILS_V3_BINDINGS"),
        "generated stream scaffold": (
            files["go_route_gen_impl"],
            "serverMessage, err := NewSweepStreamMessageState(&serverData)",
        ),
        "generated channel scaffold": (files["go_route_gen_impl"], "clientMessage, err := channel.Recv(ctx)"),
        "generated router option": (files["go_route_gen_impl"], "type GenRouterOption func(router *_GenRouter)"),
        "generated flow option": (files["go_route_gen_impl"], "func WithAssistantSessionFlow("),
        "generated flow route": (files["go_route_gen_impl"], "return flow.Serve(ctx, channel)"),
        "generated stream sender": (files["go_route_impl"], "NewSweepEventsSender("),
        "manual assistant route in impl": (files["go_route_impl"], "func (impl *Router) AssistantSession("),
        "old channel dispatcher example": (files["go_route_impl"], "DispatchAssistantClientMessage("),
        "old generated channel dispatcher": (files["go_route_messages"], "func DispatchAssistantClientMessage("),
        "old generated channel handlers": (files["go_route_messages"], "type AssistantClientMessageHandlers struct {"),
        "message union in gen_types": (files["go_route_types"], "type AssistantClientMessage struct {"),
        "user router flow field": (files["go_route_impl"], "assistantSessionFlow *AssistantSessionFlow"),
        "user router flow delegate": (files["go_route_impl"], "return flow.Serve(ctx, channel)"),
        "generated flow file": (
            workspace.golang_server_dir / "views" / "routes" / "api" / "demo" / "gen_assistant_session_flow.go",
            "type AssistantSessionFlow struct {",
        ),
        "generated stream sender file": (
            workspace.golang_server_dir / "views" / "routes" / "api" / "demo" / "gen_sweep_events_stream.go",
            "type SweepEventsSender struct {",
        ),
        "old exported assistant processor": (files["go_route_assistant_processor"], "type AssistantSessionProcessor struct{}"),
        "old exported assistant scope": (files["go_route_assistant_processor"], "type AssistantSessionScope struct {"),
        "route-prefixed input processor": (files["go_route_assistant_processor"], "OnAssistantSessionInput"),
        "route-prefixed cancel processor": (files["go_route_assistant_processor"], "OnAssistantSessionCancel"),
    }
    for label, (path, snippet) in forbidden_checks.items():
        if path.is_file() and snippet in path.read_text(encoding="utf-8"):
            validation_errors.append(label)
    if validation_errors:
        raise ExampleValidationError(
            "blueprint connection example validation failed:\n" + "\n".join(validation_errors)
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


def _raise_on_snapshot_drift(pairs: Iterable[tuple[Path, Path, str]]) -> None:
    problems: list[str] = []
    for expected, actual, label in pairs:
        problems.extend(_collect_path_diff(expected, actual, prefix=label))
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


def _collect_path_diff(expected: Path, actual: Path, prefix: str = "") -> list[str]:
    label = prefix or expected.name
    if expected.is_dir():
        if not actual.is_dir():
            return [f"{label}: missing directory"]
        return _collect_dir_diff(expected, actual, prefix=label)
    if expected.is_file():
        if not actual.is_file():
            return [f"{label}: missing file"]
        if expected.read_bytes() != actual.read_bytes():
            return [f"{label}: changed file"]
        return []
    if actual.exists():
        return [f"{label}: unexpected {actual.name}"]
    return []


def compile_generated_examples(workspace: BlueprintExampleWorkspace) -> None:
    _validate_blueprint_connection_examples(workspace)
    subprocess.run(["tsc", "-p", str(workspace.typescript_dir / "tsconfig.json"), "--noEmit"], check=True)
    subprocess.run(["go", "test", "./..."], cwd=workspace.golang_server_dir, check=True)
    subprocess.run(["go", "test", "./..."], cwd=workspace.golang_client_dir, check=True)
    _validate_kotlin_sources(workspace.kotlin_dir)
    _validate_java_sources(workspace.java_dir)
    _validate_python_sources(workspace.python_dir)
    _validate_flutter_sources(workspace.flutter_dir)
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


def compile_repo_grpc_examples(repo_root: Path) -> None:
    compile_generated_grpc_examples(_grpc_workspace(repo_root / "examples"))


def _tidy_go_module(go_dir: Path) -> None:
    subprocess.run(["go", "mod", "tidy"], cwd=go_dir, check=True)


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


def _validate_kotlin_sources(kotlin_dir: Path) -> None:
    client_dir = kotlin_dir / "client"
    server_dir = kotlin_dir / "server"
    _validate_kotlin_client_sources(client_dir)
    _validate_kotlin_server_sources(server_dir)
    _compile_kotlin_sources(client_dir, include_okhttp=True, include_ktor=False)
    _compile_kotlin_sources(server_dir, include_okhttp=False, include_ktor=True)


def _validate_kotlin_client_sources(kotlin_dir: Path) -> None:
    expected = (
        "com/example/apiblueprint/api/runtime/ApiClient.kt",
        "com/example/apiblueprint/api/runtime/GenApiClient.kt",
        "com/example/apiblueprint/api/runtime/GenApiException.kt",
        "com/example/apiblueprint/api/runtime/GenApiTransport.kt",
        "com/example/apiblueprint/api/runtime/ApiJson.kt",
        "com/example/apiblueprint/api/runtime/ApiTypes.kt",
        "com/example/apiblueprint/api/routes/api/demo/DemoApi.kt",
        "com/example/apiblueprint/api/routes/api/demo/GenDemoApi.kt",
        "com/example/apiblueprint/api/routes/api/demo/DemoTypes.kt",
        "com/example/apiblueprint/api/routes/api/hello/GenHelloApi.kt",
        "com/example/apiblueprint/api/routes/api/hello/HelloTypes.kt",
        "com/example/apiblueprint/api/routes/api/hello/HelloApi.kt",
        "com/example/apiblueprint/api/transports/http/GenHttpApiConfig.kt",
        "com/example/apiblueprint/api/transports/http/GenOkHttpApiTransport.kt",
        "com/example/apiblueprint/api/transports/http/HttpApiClient.kt",
    )
    missing = [path for path in expected if not (kotlin_dir / path).is_file()]
    if missing:
        raise ExampleValidationError("kotlin client example missing generated files:\n" + "\n".join(missing))

    types = (kotlin_dir / "com/example/apiblueprint/api/runtime/ApiTypes.kt").read_text(encoding="utf-8")
    demo_types = (kotlin_dir / "com/example/apiblueprint/api/routes/api/demo/DemoTypes.kt").read_text(
        encoding="utf-8"
    )
    hello_types = (kotlin_dir / "com/example/apiblueprint/api/routes/api/hello/HelloTypes.kt").read_text(
        encoding="utf-8"
    )
    demo_api = (kotlin_dir / "com/example/apiblueprint/api/routes/api/demo/GenDemoApi.kt").read_text(encoding="utf-8")
    hello_api = (kotlin_dir / "com/example/apiblueprint/api/routes/api/hello/GenHelloApi.kt").read_text(
        encoding="utf-8"
    )
    required_snippets = (
        "// Code generated by api-blueprint (Kotlin client); DO NOT EDIT.",
        "@Serializable",
        "public data class DemoAbcQuery",
        "public data class ApiDemoA",
        "public enum class ColorEnum",
        "public enum class ColorEnum(public val wireValue: String)",
        "@Serializable(with = StatusEnumSerializer::class)",
        "public open suspend fun abc",
        "path = \"/api/demo/abc\"",
        "responseSerializer = MapSerializer(String.serializer(), ApiHelloMap.serializer())",
        'responseEnvelope = ApiResponseEnvelope(name = "CodeMessageDataEnvelope", kind = "code_message_data"',
        '"type" to type.wireValue.toString()',
        "public open suspend fun helloWay",
    )
    haystack = "\n".join((types, demo_api, hello_api, demo_types, hello_types))
    missing_snippets = [snippet for snippet in required_snippets if snippet not in haystack]
    if missing_snippets:
        raise ExampleValidationError("kotlin client example missing expected snippets:\n" + "\n".join(missing_snippets))


def _validate_kotlin_server_sources(kotlin_dir: Path) -> None:
    expected = (
        "com/example/apiblueprint/api/runtime/ApiJson.kt",
        "com/example/apiblueprint/api/runtime/ApiServerContext.kt",
        "com/example/apiblueprint/api/runtime/ApiServerResponse.kt",
        "com/example/apiblueprint/api/runtime/GenApiException.kt",
        "com/example/apiblueprint/api/runtime/GenApiErrors.kt",
        "com/example/apiblueprint/api/runtime/GenApiErrorLookup.kt",
        "com/example/apiblueprint/api/runtime/ApiTypes.kt",
        "com/example/apiblueprint/api/routes/api/demo/DemoService.kt",
        "com/example/apiblueprint/api/routes/api/demo/DemoServiceStub.kt",
        "com/example/apiblueprint/api/routes/api/demo/GenDemoService.kt",
        "com/example/apiblueprint/api/routes/api/demo/DemoTypes.kt",
        "com/example/apiblueprint/api/transports/ktor/api/demo/GenDemoKtorRoutes.kt",
    )
    missing = [path for path in expected if not (kotlin_dir / path).is_file()]
    if missing:
        raise ExampleValidationError("kotlin server example missing generated files:\n" + "\n".join(missing))

    service = (kotlin_dir / "com/example/apiblueprint/api/routes/api/demo/GenDemoService.kt").read_text(
        encoding="utf-8"
    )
    types = (kotlin_dir / "com/example/apiblueprint/api/routes/api/demo/DemoTypes.kt").read_text(encoding="utf-8")
    ktor = (
        kotlin_dir / "com/example/apiblueprint/api/transports/ktor/api/demo/GenDemoKtorRoutes.kt"
    ).read_text(encoding="utf-8")
    haystack = "\n".join((service, types, ktor))
    required_snippets = (
        "// Code generated by api-blueprint (Kotlin server); DO NOT EDIT.",
        "public interface GenDemoService",
        "public suspend fun abc(",
        "public object AssistantClientMessageVariants",
        "public fun <R> dispatchAssistantClientMessage(",
        "public fun Route.registerDemoRoutes(",
        '"channel route is not implemented by the generated Ktor adapter"',
    )
    missing_snippets = [snippet for snippet in required_snippets if snippet not in haystack]
    if missing_snippets:
        raise ExampleValidationError("kotlin server example missing expected snippets:\n" + "\n".join(missing_snippets))


def _validate_java_sources(java_dir: Path) -> None:
    expected = (
        "client/com/example/apiblueprint/api/runtime/ApiClient.java",
        "client/com/example/apiblueprint/api/runtime/GenApiClient.java",
        "client/com/example/apiblueprint/api/routes/api/demo/DemoApi.java",
        "client/com/example/apiblueprint/api/routes/api/demo/GenDemoApi.java",
        "client/com/example/apiblueprint/api/routes/api/demo/DemoTypes.java",
        "client/com/example/apiblueprint/api/transports/http/GenJdkHttpApiTransport.java",
        "client/com/example/apiblueprint/api/transports/http/HttpApiClient.java",
        "server/com/example/apiblueprint/api/routes/api/demo/DemoService.java",
        "server/com/example/apiblueprint/api/routes/api/demo/GenDemoService.java",
        "server/com/example/apiblueprint/api/routes/api/demo/DemoTypes.java",
        "server/com/example/apiblueprint/api/routes/api/demo/DemoServiceStub.java",
        "server/com/example/apiblueprint/api/transports/http/api/demo/GenDemoController.java",
    )
    missing = [path for path in expected if not (java_dir / path).is_file()]
    if missing:
        raise ExampleValidationError("java example missing generated files:\n" + "\n".join(missing))

    snippets = {
        "client route": (
            java_dir / "client/com/example/apiblueprint/api/routes/api/demo/GenDemoApi.java",
            "public ApiTypes.ApiDemoA abc(",
        ),
        "client transport": (
            java_dir / "client/com/example/apiblueprint/api/transports/http/GenJdkHttpApiTransport.java",
            "public class GenJdkHttpApiTransport implements ApiTransport",
        ),
        "server service": (
            java_dir / "server/com/example/apiblueprint/api/routes/api/demo/GenDemoService.java",
            "public interface GenDemoService",
        ),
        "server controller": (
            java_dir / "server/com/example/apiblueprint/api/transports/http/api/demo/GenDemoController.java",
            "@RestController",
        ),
        "api error lookup": (
            java_dir / "client/com/example/apiblueprint/api/runtime/ApiErrors.java",
            "COMMONERR_TOKEN_EXPIRE",
        ),
        "binary schema": (
            java_dir / "client/com/example/apiblueprint/api/routes/api/binary/BinaryTypes.java",
            "DemoPacketWire",
        ),
    }
    missing_snippets = [
        label for label, (path, snippet) in snippets.items() if snippet not in path.read_text(encoding="utf-8")
    ]
    if missing_snippets:
        raise ExampleValidationError("java example missing expected snippets:\n" + "\n".join(missing_snippets))
    _compile_java_sources(java_dir)


def _validate_python_sources(python_dir: Path) -> None:
    expected = (
        "client/api_blueprint_example_client/api/runtime/gen_client.py",
        "client/api_blueprint_example_client/api/routes/api/demo/gen_client.py",
        "client/api_blueprint_example_client/api/transports/http/gen_client.py",
        "server/api_blueprint_example_server/api/runtime/gen_server.py",
        "server/api_blueprint_example_server/api/routes/api/demo/gen_service.py",
        "server/api_blueprint_example_server/api/transports/http/gen_server.py",
    )
    missing = [path for path in expected if not (python_dir / path).is_file()]
    if missing:
        raise ExampleValidationError("python example missing generated files:\n" + "\n".join(missing))

    snippets = {
        "client async route": (
            python_dir / "client/api_blueprint_example_client/api/routes/api/demo/gen_client.py",
            "async def abc(",
        ),
        "client transport": (
            python_dir / "client/api_blueprint_example_client/api/transports/http/gen_client.py",
            "class HttpClientTransport(ApiClientTransport):",
        ),
        "server service": (
            python_dir / "server/api_blueprint_example_server/api/routes/api/demo/gen_service.py",
            "class DemoService(Protocol):",
        ),
        "server fastapi adapter": (
            python_dir / "server/api_blueprint_example_server/api/transports/http/gen_server.py",
            "from fastapi import APIRouter",
        ),
    }
    missing_snippets = [
        label for label, (path, snippet) in snippets.items() if snippet not in path.read_text(encoding="utf-8")
    ]
    if missing_snippets:
        raise ExampleValidationError("python example missing expected snippets:\n" + "\n".join(missing_snippets))
    for path in python_dir.rglob("*.py"):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")


def _validate_flutter_sources(flutter_dir: Path) -> None:
    expected = (
        "lib/api_blueprint_example.dart",
        "lib/src/api/runtime/gen_api_client.dart",
        "lib/src/api/runtime/gen_api_transport.dart",
        "lib/src/api/runtime/gen_api_errors.dart",
        "lib/src/api/runtime/gen_api_error_lookup.dart",
        "lib/src/api/runtime/gen_api_types.dart",
        "lib/src/api/runtime/binary/gen_binary_runtime.dart",
        "lib/src/api/routes/api/demo/gen_demo_api.dart",
        "lib/src/api/routes/api/demo/gen_demo_types.dart",
        "lib/src/api/routes/api/binary/gen_binary.dart",
        "lib/src/api/transports/http/gen_http_api_transport.dart",
        "test/api_contract_test.dart",
        "test/binary_contract_test.dart",
        "test/http_transport_test.dart",
    )
    missing = [path for path in expected if not (flutter_dir / path).is_file()]
    if missing:
        raise ExampleValidationError("flutter example missing generated files:\n" + "\n".join(missing))
    subprocess.run(["dart", "pub", "get"], cwd=flutter_dir, check=True)
    subprocess.run(["dart", "analyze"], cwd=flutter_dir, check=True)
    subprocess.run(["dart", "test"], cwd=flutter_dir, check=True)


def _compile_kotlin_sources(kotlin_dir: Path, *, include_okhttp: bool, include_ktor: bool) -> None:
    gradle_bin = resolve_gradle_bin()
    if gradle_bin is None:
        raise ExampleValidationError(
            "missing Kotlin compile requirement: Gradle is required; "
            f"install `gradle` or set `{GRADLE_BIN_ENV}`."
        )

    with tempfile.TemporaryDirectory(prefix="api-blueprint-kotlin-") as temp_dir:
        project_dir = Path(temp_dir)
        source_dir = project_dir / "src/main/kotlin"
        shutil.copytree(kotlin_dir, source_dir)
        (project_dir / "settings.gradle.kts").write_text(
            'pluginManagement { repositories { gradlePluginPortal(); mavenCentral() } }\n'
            "dependencyResolutionManagement { "
            "repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS); "
            "repositories { mavenCentral() } "
            "}\n"
            'rootProject.name = "api-blueprint-kotlin-example"\n',
            encoding="utf-8",
        )
        dependencies = [
            f'    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:{KOTLINX_COROUTINES_VERSION}")',
            f'    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:{KOTLINX_SERIALIZATION_JSON_VERSION}")',
            f'    implementation("com.squareup.okio:okio:{OKIO_VERSION}")',
        ]
        if include_okhttp:
            dependencies.append(f'    implementation("com.squareup.okhttp3:okhttp:{OKHTTP_VERSION}")')
        if include_ktor:
            dependencies.append(f'    implementation("io.ktor:ktor-server-core-jvm:{KTOR_VERSION}")')
        (project_dir / "build.gradle.kts").write_text(
            f"""
plugins {{
    kotlin("jvm") version "{KOTLIN_VERSION}"
    kotlin("plugin.serialization") version "{KOTLIN_VERSION}"
}}

dependencies {{
{chr(10).join(dependencies)}
}}

java {{
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}}

kotlin {{
    compilerOptions {{
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }}
}}
            """.strip()
            + "\n",
            encoding="utf-8",
        )
        subprocess.run([gradle_bin, "--no-daemon", "compileKotlin"], cwd=project_dir, check=True)


def _compile_java_sources(java_dir: Path) -> None:
    gradle_bin = resolve_gradle_bin()
    if gradle_bin is None:
        raise ExampleValidationError(
            "missing Java compile requirement: Gradle is required; "
            f"install `gradle` or set `{GRADLE_BIN_ENV}`."
        )

    with tempfile.TemporaryDirectory(prefix="api-blueprint-java-") as temp_dir:
        project_dir = Path(temp_dir)
        source_dir = project_dir / "src/main/java"
        source_dir.mkdir(parents=True)
        for source_root in (java_dir / "client", java_dir / "server"):
            if source_root.is_dir():
                shutil.copytree(source_root / "com", source_dir / "com", dirs_exist_ok=True)
        (project_dir / "settings.gradle.kts").write_text(
            'pluginManagement { repositories { gradlePluginPortal(); mavenCentral() } }\n'
            "dependencyResolutionManagement { "
            "repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS); "
            "repositories { mavenCentral() } "
            "}\n"
            'rootProject.name = "api-blueprint-java-example"\n',
            encoding="utf-8",
        )
        (project_dir / "build.gradle.kts").write_text(
            f"""
plugins {{ java }}

dependencies {{
    implementation("com.fasterxml.jackson.core:jackson-databind:{JACKSON_DATABIND_VERSION}")
    implementation("org.springframework.boot:spring-boot-starter-web:{SPRING_BOOT_VERSION}")
}}

java {{
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}}
            """.strip()
            + "\n",
            encoding="utf-8",
        )
        subprocess.run([gradle_bin, "--no-daemon", "compileJava"], cwd=project_dir, check=True)


def validate_examples(repo_root: Path, scope: ExampleValidationScope = ExampleValidationScope.ALL) -> None:
    if scope is ExampleValidationScope.BLUEPRINT:
        validate_blueprint_examples(repo_root)
        return
    if scope is ExampleValidationScope.GRPC:
        validate_grpc_examples(repo_root)
        return
    if scope is ExampleValidationScope.WAILS_HELLO:
        validate_wails_hello_examples(repo_root)
        return

    ensure_validation_requirements(ExampleValidationScope.ALL)
    blueprint_workspace = prepare_blueprint_workspace(repo_root)
    grpc_workspace = prepare_grpc_workspace(repo_root)
    wails_hello_workspace = prepare_wails_hello_workspace(repo_root)
    try:
        regenerate_blueprint_examples(blueprint_workspace)
        regenerate_grpc_examples(grpc_workspace)
        regenerate_wails_hello_example(wails_hello_workspace)
        validate_example_snapshots(repo_root, blueprint_workspace)
        validate_grpc_snapshots(repo_root, grpc_workspace)
        validate_wails_hello_snapshots(repo_root, wails_hello_workspace)
        compile_generated_examples(blueprint_workspace)
        compile_generated_grpc_examples(grpc_workspace)
        compile_wails_hello_example(wails_hello_workspace)
    finally:
        shutil.rmtree(blueprint_workspace.root, ignore_errors=True)
        shutil.rmtree(grpc_workspace.root, ignore_errors=True)
        shutil.rmtree(wails_hello_workspace.root, ignore_errors=True)


def validate_blueprint_examples(repo_root: Path) -> None:
    ensure_validation_requirements(ExampleValidationScope.BLUEPRINT)
    blueprint_workspace = prepare_blueprint_workspace(repo_root)
    try:
        regenerate_blueprint_examples(blueprint_workspace)
        validate_example_snapshots(repo_root, blueprint_workspace)
        compile_generated_examples(blueprint_workspace)
    finally:
        shutil.rmtree(blueprint_workspace.root, ignore_errors=True)


def validate_grpc_examples(repo_root: Path) -> None:
    ensure_validation_requirements(ExampleValidationScope.GRPC)
    grpc_workspace = prepare_grpc_workspace(repo_root)
    try:
        regenerate_grpc_examples(grpc_workspace)
        validate_grpc_snapshots(repo_root, grpc_workspace)
        compile_generated_grpc_examples(grpc_workspace)
    finally:
        shutil.rmtree(grpc_workspace.root, ignore_errors=True)


def validate_wails_hello_examples(repo_root: Path) -> None:
    ensure_validation_requirements(ExampleValidationScope.WAILS_HELLO)
    wails_hello_workspace = prepare_wails_hello_workspace(repo_root)
    try:
        regenerate_wails_hello_example(wails_hello_workspace)
        validate_wails_hello_snapshots(repo_root, wails_hello_workspace)
        compile_wails_hello_example(wails_hello_workspace)
    finally:
        shutil.rmtree(wails_hello_workspace.root, ignore_errors=True)


def compile_examples(repo_root: Path, scope: ExampleValidationScope = ExampleValidationScope.ALL) -> None:
    if scope is ExampleValidationScope.BLUEPRINT:
        compile_blueprint_examples(repo_root)
        return
    if scope is ExampleValidationScope.GRPC:
        compile_grpc_examples(repo_root)
        return
    if scope is ExampleValidationScope.WAILS_HELLO:
        compile_wails_hello_examples(repo_root)
        return

    ensure_validation_requirements(ExampleValidationScope.ALL)
    blueprint_workspace = prepare_blueprint_workspace(repo_root)
    grpc_workspace = prepare_grpc_workspace(repo_root)
    wails_hello_workspace = prepare_wails_hello_workspace(repo_root)
    try:
        regenerate_blueprint_examples(blueprint_workspace)
        regenerate_grpc_examples(grpc_workspace)
        regenerate_wails_hello_example(wails_hello_workspace)
        compile_generated_examples(blueprint_workspace)
        compile_generated_grpc_examples(grpc_workspace)
        compile_wails_hello_example(wails_hello_workspace)
    finally:
        shutil.rmtree(blueprint_workspace.root, ignore_errors=True)
        shutil.rmtree(grpc_workspace.root, ignore_errors=True)
        shutil.rmtree(wails_hello_workspace.root, ignore_errors=True)


def compile_blueprint_examples(repo_root: Path) -> None:
    ensure_validation_requirements(ExampleValidationScope.BLUEPRINT)
    blueprint_workspace = prepare_blueprint_workspace(repo_root)
    try:
        regenerate_blueprint_examples(blueprint_workspace)
        compile_generated_examples(blueprint_workspace)
    finally:
        shutil.rmtree(blueprint_workspace.root, ignore_errors=True)


def compile_grpc_examples(repo_root: Path) -> None:
    ensure_validation_requirements(ExampleValidationScope.GRPC)
    grpc_workspace = prepare_grpc_workspace(repo_root)
    try:
        regenerate_grpc_examples(grpc_workspace)
        compile_generated_grpc_examples(grpc_workspace)
    finally:
        shutil.rmtree(grpc_workspace.root, ignore_errors=True)


def compile_wails_hello_examples(repo_root: Path) -> None:
    ensure_validation_requirements(ExampleValidationScope.WAILS_HELLO)
    wails_hello_workspace = prepare_wails_hello_workspace(repo_root)
    try:
        regenerate_wails_hello_example(wails_hello_workspace)
        compile_wails_hello_example(wails_hello_workspace)
    finally:
        shutil.rmtree(wails_hello_workspace.root, ignore_errors=True)


def run_golang_suite_examples(repo_root: Path, scope: ExampleValidationScope = ExampleValidationScope.BLUEPRINT) -> None:
    if scope not in (ExampleValidationScope.ALL, ExampleValidationScope.BLUEPRINT):
        raise ExampleValidationError("golang-suite mode only supports --scope blueprint")
    missing = []
    for binary in ("go", "tsc", "node"):
        if shutil.which(binary) is None:
            missing.append(f"{binary}: install {binary} and ensure it is available on PATH.")
    if missing:
        raise ExampleValidationError("golang-suite mode requires additional tooling:\n" + "\n".join(missing))
    blueprint_workspace = prepare_blueprint_workspace(repo_root)
    try:
        regenerate_blueprint_golang_suite_examples(blueprint_workspace)
        env = os.environ.copy()
        env.setdefault("API_BLUEPRINT_PYTHON", sys.executable)
        subprocess.run(["go", "run", "."], cwd=blueprint_workspace.golang_suite_dir, env=env, check=True)
    finally:
        shutil.rmtree(blueprint_workspace.root, ignore_errors=True)


def run_java_suite_examples(repo_root: Path, scope: ExampleValidationScope = ExampleValidationScope.BLUEPRINT) -> None:
    if scope not in (ExampleValidationScope.ALL, ExampleValidationScope.BLUEPRINT):
        raise ExampleValidationError("java-suite mode only supports --scope blueprint")
    gradle_bin = resolve_gradle_bin()
    if gradle_bin is None:
        raise ExampleValidationError(
            "java-suite mode requires Gradle; "
            f"install `gradle` or set `{GRADLE_BIN_ENV}` to an executable Gradle binary."
        )
    blueprint_workspace = prepare_blueprint_workspace(repo_root)
    try:
        regenerate_blueprint_java_suite_examples(blueprint_workspace)
        subprocess.run([gradle_bin, "--no-daemon", "run"], cwd=blueprint_workspace.java_suite_dir, check=True)
    finally:
        shutil.rmtree(blueprint_workspace.root, ignore_errors=True)


def refresh_examples(repo_root: Path, scope: ExampleValidationScope = ExampleValidationScope.ALL) -> None:
    ensure_validation_requirements(scope)
    if scope in (ExampleValidationScope.ALL, ExampleValidationScope.BLUEPRINT):
        regenerate_repo_blueprint_examples(repo_root)
    if scope in (ExampleValidationScope.ALL, ExampleValidationScope.GRPC):
        regenerate_repo_grpc_examples(repo_root)
    if scope in (ExampleValidationScope.ALL, ExampleValidationScope.WAILS_HELLO):
        regenerate_repo_wails_hello_example(repo_root)
    compile_examples(repo_root, scope=scope)


def _collect_dir_diff(expected: Path, actual: Path, prefix: str = "") -> list[str]:
    comparison = filecmp.dircmp(expected, actual)
    label = prefix or expected.name
    ignored = EXAMPLE_SNAPSHOT_IGNORES.get(label, frozenset())
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
            "`refresh` regenerates examples in-place and compiles them, "
            "`golang-suite` runs the manual generated Go client/server round-trip suite, "
            "and `java-suite` runs the manual generated Java client/server round-trip suite."
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


if __name__ == "__main__":
    raise SystemExit(main())
