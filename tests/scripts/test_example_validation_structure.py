from __future__ import annotations

import importlib
import subprocess
import sys

from tests.support import REPO_ROOT


def test_example_validation_is_package_with_compatibility_exports() -> None:
    module = importlib.import_module("scripts.example_validation")

    assert module.__path__
    assert module.ExampleValidationScope.BLUEPRINT.value == "blueprint"
    assert module.ExampleValidationTarget.GO_SERVER.value == "go.server"
    assert module.ExampleValidationTarget.PYTHON_HTTP.value == "python.http"
    assert module.ExampleValidationTarget.WAILS_HELLO.value == "wails.hello"
    assert callable(module.validate_examples)
    assert callable(module._prepare_blueprint_outputs)
    assert callable(module._prepare_blueprint_go_server_output)
    assert callable(module._prepare_blueprint_target_output)


def test_prepare_blueprint_go_server_output_keeps_colocated_wails_outputs(tmp_path) -> None:
    module = importlib.import_module("scripts.example_validation")
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    provider_impl = source_root / "golang" / "server" / "views" / "providers" / "impl_rsp.go"
    provider_impl.parent.mkdir(parents=True)
    provider_impl.write_text("package providers\n", encoding="utf-8")
    wails_file = target_root / "golang" / "server" / "views" / "transports" / "wailsv3" / "gen_runtime.go"
    wails_file.parent.mkdir(parents=True)
    wails_file.write_text("package wailsv3\n", encoding="utf-8")

    module._prepare_blueprint_go_server_output(source_root=source_root, target_root=target_root)

    copied_provider_impl = target_root / "golang" / "server" / "views" / "providers" / "impl_rsp.go"
    assert copied_provider_impl.read_text(encoding="utf-8") == "package providers\n"
    assert wails_file.read_text(encoding="utf-8") == "package wailsv3\n"


def test_go_server_snapshot_validation_ignores_colocated_wails_outputs(tmp_path) -> None:
    module = importlib.import_module("scripts.example_validation")
    repo_root = tmp_path / "repo"
    workspace_root = tmp_path / "workspace"
    expected_file = repo_root / "examples" / "golang" / "server" / "views" / "routes" / "api" / "gen_routes.go"
    actual_file = workspace_root / "golang" / "server" / "views" / "routes" / "api" / "gen_routes.go"
    expected_http_file = (
        repo_root / "examples" / "golang" / "server" / "views" / "transports" / "http" / "gen_mount.go"
    )
    actual_http_file = workspace_root / "golang" / "server" / "views" / "transports" / "http" / "gen_mount.go"
    wails_file = (
        repo_root
        / "examples"
        / "golang"
        / "server"
        / "views"
        / "transports"
        / "wailsv3"
        / "gen_runtime.go"
    )
    expected_file.parent.mkdir(parents=True)
    actual_file.parent.mkdir(parents=True)
    expected_http_file.parent.mkdir(parents=True)
    actual_http_file.parent.mkdir(parents=True)
    wails_file.parent.mkdir(parents=True)
    expected_file.write_text("package api\n", encoding="utf-8")
    actual_file.write_text("package api\n", encoding="utf-8")
    expected_http_file.write_text("package http\n", encoding="utf-8")
    actual_http_file.write_text("package http\n", encoding="utf-8")
    wails_file.write_text("package wailsv3\n", encoding="utf-8")
    workspace = module._blueprint_workspace(workspace_root)

    module.validate_blueprint_go_server_snapshots(repo_root, workspace)


def test_example_validation_legacy_script_entrypoint_still_works() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/example_validation.py", "--help"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Validate or refresh generated example snapshots" in result.stdout
    assert "--scope" in result.stdout
    assert "--target" in result.stdout
    assert "typescript.client" in result.stdout
    assert "wails.hello" in result.stdout
