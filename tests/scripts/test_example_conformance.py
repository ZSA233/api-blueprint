from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import example_validation
from scripts.example_conformance import cli, manifest, reporter, runner, scenarios, tools


def test_manifest_marks_first_phase_capabilities() -> None:
    clients = manifest.client_manifest()

    assert clients["go"].supports_rpc is True
    assert clients["go"].supports_sse is False
    assert clients["typescript"].supports_websocket is True
    assert clients["flutter"].supports_sse is True
    assert clients["kotlin"].supports_rpc is True
    assert clients["kotlin"].supports_sse is False
    assert clients["kotlin"].connection_policy == "unsupported-contract"


def test_scenario_registry_covers_required_dsl_categories() -> None:
    coverage = scenarios.coverage_by_category()

    required = {
        "query",
        "json",
        "form",
        "binary",
        "raw",
        "xml",
        "typed-error",
        "sse",
        "websocket",
        "naming-conflict",
        "multi-blueprint",
        "envelope",
    }
    assert required <= set(coverage)
    assert "go" in coverage["binary"]
    assert "typescript" in coverage["websocket"]
    assert "flutter" in coverage["sse"]
    assert "kotlin" in coverage["form"]


def test_filter_scenarios_rejects_unknown_names() -> None:
    with pytest.raises(ValueError, match="unknown conformance scenario"):
        scenarios.filter_scenarios(["missing"])


def test_prepare_blueprint_outputs_preserves_kotlin_conformance_source(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    conformance_file = source_root / "kotlin" / "conformance" / "Conformance.kt"
    conformance_file.parent.mkdir(parents=True)
    conformance_file.write_text("package com.example.apiblueprint.conformance\n", encoding="utf-8")

    example_validation._prepare_blueprint_outputs(source_root=source_root, target_root=target_root)

    assert (target_root / "kotlin" / "conformance" / "Conformance.kt").read_text(encoding="utf-8") == (
        "package com.example.apiblueprint.conformance\n"
    )


def test_reporter_suppresses_success_output_and_reports_stage(capsys: pytest.CaptureFixture[str]) -> None:
    reporter.run_stage("generate examples", lambda: print("generated noisy file list"))

    captured = capsys.readouterr()
    assert "generate examples ... ok" in captured.out
    assert "generated noisy file list" not in captured.out
    assert captured.err == ""


def test_reporter_supports_forced_color(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("FORCE_COLOR", "1")

    reporter.run_stage("server go", lambda: "http://127.0.0.1", success_detail=lambda value: value)

    captured = capsys.readouterr()
    assert "\x1b[32mok\x1b[0m http://127.0.0.1" in captured.out


def test_reporter_replays_captured_output_on_failure(capsys: pytest.CaptureFixture[str]) -> None:
    def fail() -> None:
        print("stdout before failure")
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        reporter.run_stage("flutter [sse]", fail)

    captured = capsys.readouterr()
    assert "flutter [sse] ... failed" in captured.out
    assert "--- flutter [sse] output ---" in captured.err
    assert "stdout before failure" in captured.err


def test_reporter_prints_scenario_subitems(capsys: pytest.CaptureFixture[str]) -> None:
    reporter.print_group("flutter")
    reporter.run_sub_stage("flutter/sse", lambda: None)
    reporter.run_sub_stage("flutter/websocket", lambda: None)

    captured = capsys.readouterr()
    assert "flutter:" in captured.out
    assert "  - flutter/sse ... ok" in captured.out
    assert "  - flutter/websocket ... ok" in captured.out


def test_runner_reports_server_and_client_matrix_without_client_noise(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_server = SimpleNamespace(
        base_url="http://127.0.0.1:12345",
        output_path=Path(".conformance-server.log"),
        stop=lambda: None,
    )
    fake_workspace = SimpleNamespace(
        blueprint=SimpleNamespace(golang_server_dir=Path(".")),
    )
    calls: list[tuple[str, str]] = []

    def fake_run_client(ws: object, client: str, base_url: str, selected_scenarios: tuple[scenarios.Scenario, ...]) -> None:
        print("client noisy output")
        calls.append((client, ",".join(scenario.name for scenario in selected_scenarios)))

    monkeypatch.setattr(runner.server, "start_go_server", lambda server_dir: fake_server)
    monkeypatch.setattr(runner.server, "cleanup_server_log", lambda path: None)
    monkeypatch.setattr(runner, "_run_client", fake_run_client)

    runner._run_against_workspace(
        fake_workspace,  # type: ignore[arg-type]
        server_name="go",
        clients=("flutter",),
        selected_scenarios=scenarios.filter_scenarios(("sse", "websocket")),
    )

    captured = capsys.readouterr()
    assert "server go ... ok http://127.0.0.1:12345" in captured.out
    assert "flutter:" in captured.out
    assert "  - flutter/sse ... ok" in captured.out
    assert "  - flutter/websocket ... ok" in captured.out
    assert "client noisy output" not in captured.out
    assert calls == [("flutter", "sse"), ("flutter", "websocket")]


def test_cli_list_reports_servers_clients_and_scenarios(capsys: pytest.CaptureFixture[str]) -> None:
    result = cli.main(["list"])

    assert result == 0
    output = capsys.readouterr().out
    assert "servers:" in output
    assert "- go" in output
    assert "clients:" in output
    assert "- kotlin rpc=yes sse=no websocket=no" in output
    assert "scenarios:" in output
    assert "- binary" in output


def test_cli_run_invokes_runner_with_filters(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[Path, str, tuple[str, ...], tuple[str, ...], bool]] = []

    def fake_run(
        repo_root: Path,
        *,
        server: str,
        clients: tuple[str, ...],
        scenario_names: tuple[str, ...],
        keep_workspace: bool,
    ) -> None:
        calls.append((repo_root, server, clients, scenario_names, keep_workspace))

    monkeypatch.setattr(cli.runner, "run_conformance", fake_run)

    result = cli.main(
        [
            "--repo-root",
            str(tmp_path),
            "run",
            "--server",
            "go",
            "--clients",
            "go,flutter",
            "--scenario",
            "rpc,binary",
            "--keep-workspace",
        ]
    )

    assert result == 0
    assert calls == [(tmp_path.resolve(), "go", ("go", "flutter"), ("rpc", "binary"), True)]


def test_cli_generate_invokes_runner(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[Path, bool]] = []

    def fake_generate(repo_root: Path, *, keep_workspace: bool) -> None:
        calls.append((repo_root, keep_workspace))

    monkeypatch.setattr(cli.runner, "generate_conformance_workspace", fake_generate)

    result = cli.main(["--repo-root", str(tmp_path), "generate", "--keep-workspace"])

    assert result == 0
    assert calls == [(tmp_path.resolve(), True)]


def test_cli_check_and_refresh_invoke_runner(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    check_calls: list[tuple[Path, str, tuple[str, ...], tuple[str, ...], bool]] = []
    refresh_calls: list[tuple[Path, str, tuple[str, ...], tuple[str, ...]]] = []

    def fake_check(
        repo_root: Path,
        *,
        server_name: str,
        clients: tuple[str, ...],
        scenario_names: tuple[str, ...],
        keep_workspace: bool,
    ) -> None:
        check_calls.append((repo_root, server_name, clients, scenario_names, keep_workspace))

    def fake_refresh(
        repo_root: Path,
        *,
        server_name: str,
        clients: tuple[str, ...],
        scenario_names: tuple[str, ...],
    ) -> None:
        refresh_calls.append((repo_root, server_name, clients, scenario_names))

    monkeypatch.setattr(cli.runner, "check_conformance", fake_check)
    monkeypatch.setattr(cli.runner, "refresh_and_check", fake_refresh)

    check_result = cli.main(
        [
            "--repo-root",
            str(tmp_path),
            "check",
            "--clients",
            "typescript,kotlin",
            "--scenario",
            "form,error",
            "--keep-workspace",
        ]
    )
    refresh_result = cli.main(
        [
            "--repo-root",
            str(tmp_path),
            "refresh",
            "--clients",
            "flutter",
            "--scenario",
            "sse",
        ]
    )

    assert check_result == 0
    assert refresh_result == 0
    assert check_calls == [(tmp_path.resolve(), "go", ("typescript", "kotlin"), ("form", "error"), True)]
    assert refresh_calls == [(tmp_path.resolve(), "go", ("flutter",), ("sse",))]


def test_cli_rejects_unsupported_server(capsys: pytest.CaptureFixture[str]) -> None:
    result = cli.main(["run", "--server", "java"])

    assert result == 1
    assert "server java is planned but not enabled" in capsys.readouterr().err


def test_tools_reports_missing_language_binaries(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_which(binary: str) -> str | None:
        return None if binary in {"go", "dart", "tsc"} else f"/usr/bin/{binary}"

    monkeypatch.setattr(tools.shutil, "which", fake_which)
    monkeypatch.setattr(tools.example_validation, "resolve_gradle_bin", lambda: None)

    missing = tools.missing_tools_for_clients(("go", "typescript", "kotlin", "flutter"))

    assert "go: required for go conformance" in missing
    assert "tsc: required for typescript conformance" in missing
    assert "gradle: required for kotlin conformance; set API_BLUEPRINT_GRADLE_BIN if needed" in missing
    assert "dart: required for flutter conformance" in missing


def test_tools_reports_go_binary_required_for_go_server(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tools.shutil, "which", lambda binary: None if binary == "go" else f"/usr/bin/{binary}")

    missing = tools.missing_tools_for_targets("go", ("flutter",))

    assert "go: required for go conformance server" in missing
