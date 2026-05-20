from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .constants import GRADLE_BIN_ENV
from .compile import (
    compile_generated_examples,
    compile_generated_grpc_examples,
    compile_wails_hello_example,
)
from .generate import (
    regenerate_blueprint_examples,
    regenerate_blueprint_golang_suite_examples,
    regenerate_blueprint_java_suite_examples,
    regenerate_grpc_examples,
    regenerate_repo_blueprint_examples,
    regenerate_repo_grpc_examples,
    regenerate_repo_wails_hello_example,
    regenerate_wails_hello_example,
)
from .models import ExampleValidationError, ExampleValidationScope
from .snapshot import validate_example_snapshots, validate_grpc_snapshots, validate_wails_hello_snapshots
from .tools import ensure_validation_requirements, resolve_gradle_bin
from .workspace import prepare_blueprint_workspace, prepare_grpc_workspace, prepare_wails_hello_workspace

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
