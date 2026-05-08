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
GRADLE_BIN_ENV = "API_BLUEPRINT_GRADLE_BIN"
WAILS_V2_BIN_ENV = "API_BLUEPRINT_WAILS_V2_BIN"
WAILS_V3_BIN_ENV = "API_BLUEPRINT_WAILS_V3_BIN"

BLUEPRINT_GOLANG_PRESERVED = (
    "go.mod",
    "go.sum",
    "main.go",
    "views/routes/api/demo/impl.go",
)
BLUEPRINT_TYPESCRIPT_PRESERVED = (
    ".vscode/settings.json",
    "index.ts",
    "tsconfig.json",
)
BLUEPRINT_KOTLIN_PRESERVED = ()
BLUEPRINT_PYTHON_PRESERVED = ()
WAILS_HELLO_GOLANG_PRESERVED = (
    "go.mod",
    "go.sum",
    "views/routes/api/hello/impl.go",
)
WAILS_HELLO_TYPESCRIPT_PRESERVED = ("tsconfig.json",)
GRPC_GO_PRESERVED = ("go.mod", "go.sum")
GRPC_PYTHON_PRESERVED = ()


class ExampleValidationError(RuntimeError):
    pass


class ExampleValidationMode(StrEnum):
    CHECK = "check"
    COMPILE = "compile"
    REFRESH = "refresh"


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
    typescript_dir: Path
    kotlin_dir: Path
    python_dir: Path
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
        typescript_dir=root / "typescript",
        kotlin_dir=root / "kotlin",
        python_dir=root / "python",
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
    _prepare_output_dir(
        target_root / "golang",
        _capture_relative_files(source_root / "golang", BLUEPRINT_GOLANG_PRESERVED),
    )
    _prepare_output_dir(
        target_root / "typescript",
        _capture_relative_files(source_root / "typescript", BLUEPRINT_TYPESCRIPT_PRESERVED),
    )
    _prepare_output_dir(
        target_root / "kotlin",
        _capture_relative_files(source_root / "kotlin", BLUEPRINT_KOTLIN_PRESERVED),
    )
    _prepare_output_dir(
        target_root / "python",
        _capture_relative_files(source_root / "python", BLUEPRINT_PYTHON_PRESERVED),
    )


def _prepare_contract_outputs(target_root: Path) -> None:
    for name in (
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
    generator.generate(workspace.config_path, target_ids=("contract", "http", "http.python", "wails.v2", "wails.v3"))
    _tidy_go_module(workspace.golang_dir)


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
            (examples_root / "api-blueprint.contract.json", workspace.root / "api-blueprint.contract.json", "contract/json"),
            (examples_root / "api-blueprint.contract.md", workspace.root / "api-blueprint.contract.md", "contract/markdown"),
            (examples_root / "api-blueprint.agent.json", workspace.root / "api-blueprint.agent.json", "contract/agent-json"),
            (examples_root / "api-blueprint.agent.md", workspace.root / "api-blueprint.agent.md", "contract/agent-markdown"),
            (examples_root / "api-blueprint.contract.d", workspace.root / "api-blueprint.contract.d", "contract/shards"),
            (examples_root / "golang", workspace.golang_dir, "blueprint/golang"),
            (examples_root / "typescript", workspace.typescript_dir, "blueprint/typescript"),
            (examples_root / "kotlin", workspace.kotlin_dir, "blueprint/kotlin"),
            (examples_root / "python", workspace.python_dir, "blueprint/python"),
        )
    )
    _validate_blueprint_connection_examples(workspace)


def _validate_blueprint_connection_examples(workspace: BlueprintExampleWorkspace) -> None:
    files = {
        "go_route_interface": workspace.golang_dir / "views" / "routes" / "api" / "demo" / "gen_interface.go",
        "go_route_gen_impl": workspace.golang_dir / "views" / "routes" / "api" / "demo" / "gen_impl.go",
        "go_route_impl": workspace.golang_dir / "views" / "routes" / "api" / "demo" / "impl.go",
        "go_http_adapter": workspace.golang_dir / "views" / "transports" / "http" / "api" / "demo" / "gen_interface.go",
        "go_wails_v3_service": workspace.golang_dir
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
        "ts_wails_v3_bindings": workspace.typescript_dir
        / "api"
        / "transports"
        / "wailsv3"
        / "gen_bindings.ts",
        "ts_route_client": workspace.typescript_dir / "api" / "routes" / "api" / "demo" / "gen_client.ts",
        "ts_route_models": workspace.typescript_dir / "api" / "routes" / "api" / "demo" / "gen_models.ts",
    }
    missing_files = [label for label, path in files.items() if not path.is_file()]
    if missing_files:
        raise ExampleValidationError("blueprint connection example missing generated files:\n" + "\n".join(missing_files))

    checks = {
        "go stream handler": (
            files["go_route_interface"],
            "SweepEvents(\n"
            "\t\tctx *CTX_SweepEvents,\n"
            "\t\tstream providers.Stream[OPEN_SweepEvents, SweepStreamMessage, CLOSE_SweepEvents],\n"
            "\t) error",
        ),
        "go channel handler": (
            files["go_route_interface"],
            "AssistantSession(\n"
            "\t\tctx *CTX_AssistantSession,\n"
            "\t\tchannel providers.Channel[OPEN_AssistantSession, AssistantServerMessage, AssistantClientMessage, CLOSE_AssistantSession],\n"
            "\t) error",
        ),
        "go stream manual example": (
            files["go_route_impl"],
            "serverMessage, err := NewSweepStreamMessageState(&serverData)",
        ),
        "go channel manual example": (files["go_route_impl"], "clientMessage, err := channel.Recv(ctx)"),
        "http stream adapter": (files["go_http_adapter"], "httptransport.STREAM("),
        "http channel adapter": (files["go_http_adapter"], "httptransport.CHANNEL("),
        "wails stream event base": (
            files["go_wails_v3_service"],
            '"api.demo.stream.sweepevents",\n\t\t"api_blueprint.stream.api.demo.stream.sweepevents",',
        ),
        "wails channel event base": (
            files["go_wails_v3_service"],
            '"api.demo.channel.assistantsession",\n\t\t"api_blueprint.channel.api.demo.channel.assistantsession",',
        ),
        "typescript stream client": (files["ts_route_client"], "subscribeSweepEvents("),
        "typescript channel client": (files["ts_route_client"], "openAssistantSession("),
        "typescript stream union": (
            files["ts_route_models"],
            "export type SweepStreamMessage =\n"
            '  | { type: "state"; data: SweepState }\n'
            '  | { type: "progress"; data: SweepProgress }\n'
            '  | { type: "log"; data: SweepLog };',
        ),
        "typescript channel union": (
            files["ts_route_models"],
            "export type AssistantClientMessage =\n"
            '  | { type: "input"; data: AssistantInput }\n'
            '  | { type: "cancel"; data: AssistantCancel };',
        ),
        "wails v3 bindings import": (
            files["ts_wails_v3_transport"],
            'import { WAILS_V3_BINDINGS } from "./gen_bindings";',
        ),
        "wails v3 bindings manifest": (
            files["ts_wails_v3_bindings"],
            '"demo.DemoService.OpenAssistantSession": "demo/views/transports/wailsv3/api/demo.DemoService.OpenAssistantSession",',
        ),
    }
    validation_errors = []
    for label, (path, snippet) in checks.items():
        if snippet not in path.read_text(encoding="utf-8"):
            validation_errors.append(label)
    forbidden_checks = {
        "http stream explicit type args": (files["go_http_adapter"], "httptransport.STREAM["),
        "http channel explicit type args": (files["go_http_adapter"], "httptransport.CHANNEL["),
        "wails envelope explicit type args": (files["go_wails_v3_service"], "wailstransport.EnvelopeToReq["),
        "wails response wrapper explicit type args": (files["go_wails_v3_service"], "WrapRSP_JSON_GeneralWrapper["),
        "inline wails v3 bindings manifest": (files["ts_wails_v3_transport"], "const WAILS_V3_BINDINGS"),
        "generated stream scaffold": (
            files["go_route_gen_impl"],
            "serverMessage, err := NewSweepStreamMessageState(&serverData)",
        ),
        "generated channel scaffold": (files["go_route_gen_impl"], "clientMessage, err := channel.Recv(ctx)"),
    }
    for label, (path, snippet) in forbidden_checks.items():
        if snippet in path.read_text(encoding="utf-8"):
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
    subprocess.run(["go", "test", "./..."], cwd=workspace.golang_dir, check=True)
    _validate_kotlin_sources(workspace.kotlin_dir)
    _validate_python_sources(workspace.python_dir)
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
    subprocess.run(["go", "test", "./..."], cwd=workspace.golang_dir, check=True)
    _validate_kotlin_sources(workspace.kotlin_dir)
    _validate_python_sources(workspace.python_dir)


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
    expected = (
        "com/example/apiblueprint/api/runtime/ApiClient.kt",
        "com/example/apiblueprint/api/runtime/GenApiClient.kt",
        "com/example/apiblueprint/api/runtime/GenApiException.kt",
        "com/example/apiblueprint/api/runtime/GenApiTransport.kt",
        "com/example/apiblueprint/api/runtime/GenModels.kt",
        "com/example/apiblueprint/api/routes/api/demo/DemoApi.kt",
        "com/example/apiblueprint/api/routes/api/demo/GenDemoApi.kt",
        "com/example/apiblueprint/api/routes/api/demo/GenDemoApiModels.kt",
        "com/example/apiblueprint/api/routes/api/hello/GenHelloApi.kt",
        "com/example/apiblueprint/api/routes/api/hello/GenHelloApiModels.kt",
        "com/example/apiblueprint/api/routes/api/hello/HelloApi.kt",
        "com/example/apiblueprint/api/transports/http/GenHttpApiConfig.kt",
        "com/example/apiblueprint/api/transports/http/GenOkHttpApiTransport.kt",
        "com/example/apiblueprint/api/transports/http/HttpApiClient.kt",
    )
    missing = [path for path in expected if not (kotlin_dir / path).is_file()]
    if missing:
        raise ExampleValidationError("kotlin example missing generated files:\n" + "\n".join(missing))

    models = (kotlin_dir / "com/example/apiblueprint/api/runtime/GenModels.kt").read_text(encoding="utf-8")
    demo_models = (kotlin_dir / "com/example/apiblueprint/api/routes/api/demo/GenDemoApiModels.kt").read_text(
        encoding="utf-8"
    )
    hello_models = (kotlin_dir / "com/example/apiblueprint/api/routes/api/hello/GenHelloApiModels.kt").read_text(
        encoding="utf-8"
    )
    demo_api = (kotlin_dir / "com/example/apiblueprint/api/routes/api/demo/GenDemoApi.kt").read_text(encoding="utf-8")
    hello_api = (kotlin_dir / "com/example/apiblueprint/api/routes/api/hello/GenHelloApi.kt").read_text(
        encoding="utf-8"
    )
    required_snippets = (
        "// Code generated by api-blueprint; DO NOT EDIT.",
        "@Serializable",
        "public data class DemoAbcQuery",
        "public data class ApiDemoA",
        "public enum class ColorEnum",
        "public enum class ColorEnum(public val wireValue: String)",
        "@Serializable(with = StatusEnumSerializer::class)",
        "public open suspend fun abc",
        "path = \"/api/demo/abc\"",
        "responseSerializer = GeneralResponse.serializer(MapSerializer(String.serializer(), ApiHelloMap.serializer()))",
        '"type" to type.wireValue.toString()',
        "public open suspend fun helloWay",
    )
    haystack = "\n".join((models, demo_api, hello_api, demo_models, hello_models))
    missing_snippets = [snippet for snippet in required_snippets if snippet not in haystack]
    if missing_snippets:
        raise ExampleValidationError("kotlin example missing expected snippets:\n" + "\n".join(missing_snippets))
    _compile_kotlin_sources(kotlin_dir)


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


def _compile_kotlin_sources(kotlin_dir: Path) -> None:
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
        (project_dir / "build.gradle.kts").write_text(
            f"""
plugins {{
    kotlin("jvm") version "{KOTLIN_VERSION}"
    kotlin("plugin.serialization") version "{KOTLIN_VERSION}"
}}

dependencies {{
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:{KOTLINX_COROUTINES_VERSION}")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:{KOTLINX_SERIALIZATION_JSON_VERSION}")
    implementation("com.squareup.okhttp3:okhttp:{OKHTTP_VERSION}")
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
        else:
            refresh_examples(repo_root, scope=scope)
    except (ExampleValidationError, FileNotFoundError, ModuleNotFoundError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
