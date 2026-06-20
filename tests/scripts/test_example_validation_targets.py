from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.example_validation import runner, tools
from scripts.example_validation.models import ExampleValidationScope, ExampleValidationTarget


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        (ExampleValidationTarget.GO_CLIENT, "go.client"),
        (ExampleValidationTarget.TYPESCRIPT_CLIENT, "typescript.client"),
        (ExampleValidationTarget.PYTHON_HTTP, "python.http"),
        (ExampleValidationTarget.KOTLIN_HTTP, "kotlin.http"),
        (ExampleValidationTarget.JAVA_HTTP, "java.http"),
        (ExampleValidationTarget.FLUTTER_CLIENT, "flutter.client"),
        (ExampleValidationTarget.SWIFT_CLIENT, "swift.client"),
        (ExampleValidationTarget.WAILS_BLUEPRINT, "wails.blueprint"),
    ],
)
def test_validate_examples_dispatches_blueprint_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    target: ExampleValidationTarget,
    expected: str,
) -> None:
    calls: list[tuple[str, str]] = []
    workspace = SimpleNamespace(root=tmp_path / "workspace")

    monkeypatch.setattr(runner, "ensure_target_validation_requirements", lambda item: calls.append(("ensure", item.value)))
    monkeypatch.setattr(runner, "prepare_blueprint_workspace", lambda repo_root: workspace)
    monkeypatch.setattr(
        runner,
        "regenerate_blueprint_target_example",
        lambda ws, item: calls.append(("generate", item.value)),
    )
    monkeypatch.setattr(
        runner,
        "validate_blueprint_target_snapshots",
        lambda repo_root, ws, item: calls.append(("snapshot", item.value)),
    )
    monkeypatch.setattr(
        runner,
        "compile_generated_blueprint_target_example",
        lambda ws, item: calls.append(("compile", item.value)),
    )
    monkeypatch.setattr(runner.shutil, "rmtree", lambda root, ignore_errors: calls.append(("cleanup", str(root))))

    runner.validate_examples(tmp_path, scope=ExampleValidationScope.BLUEPRINT, target=target)

    assert calls == [
        ("ensure", expected),
        ("generate", expected),
        ("snapshot", expected),
        ("compile", expected),
        ("cleanup", str(workspace.root)),
    ]


@pytest.mark.parametrize(
    ("target", "expected_call"),
    [
        (ExampleValidationTarget.GRPC, "grpc"),
        (ExampleValidationTarget.WAILS_HELLO, "wails"),
    ],
)
def test_validate_examples_dispatches_non_blueprint_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    target: ExampleValidationTarget,
    expected_call: str,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(runner, "validate_grpc_examples", lambda repo_root: calls.append("grpc"))
    monkeypatch.setattr(runner, "validate_wails_hello_examples", lambda repo_root: calls.append("wails"))

    runner.validate_examples(tmp_path, scope=ExampleValidationScope.ALL, target=target)

    assert calls == [expected_call]


def test_go_client_target_requirements_do_not_require_unrelated_toolchains(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tools.shutil, "which", lambda binary: None if binary == "go" else f"/usr/bin/{binary}")
    monkeypatch.setattr(tools, "resolve_gradle_bin", lambda: None)
    monkeypatch.setattr(tools, "resolve_wails_bin", lambda env, default: None)

    missing = tools.collect_missing_target_validation_requirements(ExampleValidationTarget.GO_CLIENT)

    assert missing == ("go: install Go and ensure `go` is available on PATH.",)


def test_grpc_target_requirements_are_protocol_specific(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_which(binary: str) -> str | None:
        return None if binary in {"protoc", "protoc-gen-go", "go"} else f"/usr/bin/{binary}"

    monkeypatch.setattr(tools.shutil, "which", fake_which)
    monkeypatch.setattr(tools.importlib.util, "find_spec", lambda name: None if name == "grpc_tools" else object())

    missing = tools.collect_missing_target_validation_requirements(ExampleValidationTarget.GRPC)

    assert any(item.startswith("protoc:") for item in missing)
    assert any(item.startswith("protoc-gen-go:") for item in missing)
    assert any(item.startswith("go:") for item in missing)
    assert any(item.startswith("grpcio-tools:") for item in missing)
    assert not any(item.startswith("dart:") or item.startswith("gradle:") or item.startswith("wails:") for item in missing)
