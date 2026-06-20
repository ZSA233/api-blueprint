from __future__ import annotations

import importlib.util
import os
import shutil
from pathlib import Path

from .constants import GO_ENUM_VERSION, GRADLE_BIN_ENV, SWIFT_BIN_ENV, WAILS_V2_BIN_ENV, WAILS_V3_BIN_ENV
from .models import ExampleValidationError, ExampleValidationScope


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


def resolve_swift_bin() -> str | None:
    configured = os.environ.get(SWIFT_BIN_ENV)
    if configured:
        configured_path = Path(configured).expanduser()
        if configured_path.is_file():
            return str(configured_path)
        resolved = shutil.which(configured)
        if resolved is not None:
            return resolved
    return shutil.which("swift")


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


def collect_missing_go_server_validation_requirements() -> tuple[str, ...]:
    missing: list[str] = []
    for name, guidance in (
        ("go", "install Go and ensure `go` is available on PATH."),
        (
            "go-enum",
            "install it with `go install github.com/abice/go-enum@"
            + GO_ENUM_VERSION
            + "`.",
        ),
    ):
        if shutil.which(name) is None:
            missing.append(f"{name}: {guidance}")
    return tuple(missing)


def ensure_validation_requirements(scope: ExampleValidationScope = ExampleValidationScope.ALL) -> None:
    missing = collect_missing_validation_requirements(scope)
    if not missing:
        return
    raise ExampleValidationError(
        "example validation requires additional tooling:\n"
        + "\n".join(f"- {item}" for item in missing)
    )


def ensure_go_server_validation_requirements() -> None:
    missing = collect_missing_go_server_validation_requirements()
    if not missing:
        return
    raise ExampleValidationError(
        "go.server example validation requires additional tooling:\n"
        + "\n".join(f"- {item}" for item in missing)
    )
