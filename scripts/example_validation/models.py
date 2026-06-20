from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

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


class ExampleValidationTarget(StrEnum):
    ALL = "all"
    GO_SERVER = "go.server"


@dataclass(frozen=True)
class BlueprintExampleWorkspace:
    root: Path
    config_path: Path
    golang_dir: Path
    golang_server_dir: Path
    golang_client_dir: Path
    golang_suite_dir: Path
    golang_conformance_dir: Path
    typescript_dir: Path
    kotlin_dir: Path
    kotlin_client_dir: Path
    kotlin_server_dir: Path
    kotlin_conformance_dir: Path
    java_dir: Path
    java_client_dir: Path
    java_server_dir: Path
    java_suite_dir: Path
    java_conformance_dir: Path
    python_dir: Path
    flutter_dir: Path
    swift_dir: Path
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
