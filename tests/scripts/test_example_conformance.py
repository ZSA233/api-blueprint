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
    assert clients["kotlin"].supports_sse is True
    assert clients["kotlin"].supports_websocket is True
    assert clients["kotlin"].connection_policy == "native"


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
    assert "kotlin" in coverage["sse"]
    assert "kotlin" in coverage["websocket"]
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


def test_kotlin_conformance_harness_shuts_down_okhttp_clients() -> None:
    text = (Path(__file__).resolve().parents[2] / "examples/kotlin/conformance/Conformance.kt").read_text(
        encoding="utf-8"
    )

    assert "import okhttp3.OkHttpClient" in text
    assert "dispatcher.executorService.shutdown()" in text
    assert "connectionPool.evictAll()" in text


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

    class FakePreparedRunner:
        def run(self, base_url: str, scenario_arg: str) -> None:
            print("client noisy output")
            calls.append((base_url, scenario_arg))

        def close(self) -> None:
            calls.append(("closed", ""))

    monkeypatch.setattr(runner.server, "start_go_server", lambda server_dir: fake_server)
    monkeypatch.setattr(runner.server, "cleanup_server_log", lambda path: None)
    monkeypatch.setattr(runner, "_prepare_client_runner", lambda ws, client: FakePreparedRunner())

    runner._run_against_workspace(
        fake_workspace,  # type: ignore[arg-type]
        server_name="go",
        clients=("flutter",),
        selected_scenarios=scenarios.filter_scenarios(("sse", "websocket")),
    )

    captured = capsys.readouterr()
    assert "server go ... ok http://127.0.0.1:12345" in captured.out
    assert "flutter:" in captured.out
    assert "  - flutter/setup ... ok" in captured.out
    assert "  - flutter/sse ... ok" in captured.out
    assert "  - flutter/websocket ... ok" in captured.out
    assert "client noisy output" not in captured.out
    assert calls == [("http://127.0.0.1:12345", "sse"), ("http://127.0.0.1:12345", "websocket"), ("closed", "")]


def test_runner_prepares_each_client_once_and_runs_each_scenario(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_server = SimpleNamespace(
        base_url="http://127.0.0.1:12345",
        output_path=Path(".conformance-server.log"),
        stop=lambda: None,
    )
    fake_workspace = SimpleNamespace(
        blueprint=SimpleNamespace(
            golang_server_dir=Path("."),
            kotlin_client_dir=Path("kotlin/client"),
            kotlin_conformance_dir=Path("kotlin/conformance"),
        ),
    )
    calls: list[tuple[str, str, str]] = []

    class FakePreparedRunner:
        def __init__(self, client: str):
            self.client = client

        def run(self, base_url: str, scenario_arg: str) -> None:
            calls.append((self.client, base_url, scenario_arg))

        def close(self) -> None:
            calls.append((self.client, "closed", ""))

    monkeypatch.setattr(runner.server, "start_go_server", lambda server_dir: fake_server)
    monkeypatch.setattr(runner.server, "cleanup_server_log", lambda path: None)
    monkeypatch.setattr(runner, "_prepare_client_runner", lambda ws, client: FakePreparedRunner(client))

    runner._run_against_workspace(
        fake_workspace,  # type: ignore[arg-type]
        server_name="go",
        clients=("typescript", "kotlin"),
        selected_scenarios=scenarios.filter_scenarios(("sse", "websocket")),
    )

    captured = capsys.readouterr()
    assert "typescript:" in captured.out
    assert "  - typescript/setup ... ok" in captured.out
    assert "  - typescript/sse ... ok" in captured.out
    assert "  - typescript/websocket ... ok" in captured.out
    assert "kotlin:" in captured.out
    assert "  - kotlin/setup ... ok" in captured.out
    assert "  - kotlin/sse ... ok" in captured.out
    assert "  - kotlin/websocket ... ok" in captured.out
    assert calls == [
        ("typescript", "http://127.0.0.1:12345", "sse"),
        ("typescript", "http://127.0.0.1:12345", "websocket"),
        ("typescript", "closed", ""),
        ("kotlin", "http://127.0.0.1:12345", "sse"),
        ("kotlin", "http://127.0.0.1:12345", "websocket"),
        ("kotlin", "closed", ""),
    ]


def test_prepare_typescript_runner_compiles_once_and_reuses_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[tuple[str, ...], Path | None]] = []

    def fake_run(args: list[str], cwd: Path | None = None, check: bool = False, **kwargs: object) -> None:
        calls.append((tuple(args), cwd))

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    prepared = runner._prepare_typescript_runner(tmp_path)
    try:
        prepared.run("http://127.0.0.1:12345", "sse")
        prepared.run("http://127.0.0.1:12345", "websocket")
    finally:
        prepared.close()

    tsc_calls = [call for call in calls if call[0][0] == "tsc"]
    node_calls = [call for call in calls if call[0][0] == "node"]
    assert len(tsc_calls) == 1
    assert [call[0][-2:] for call in node_calls] == [
        ("http://127.0.0.1:12345", "sse"),
        ("http://127.0.0.1:12345", "websocket"),
    ]


def test_prepare_go_runner_builds_once_and_reuses_binary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[tuple[str, ...], Path | None]] = []

    def fake_run(args: list[str], cwd: Path | None = None, check: bool = False, **kwargs: object) -> None:
        calls.append((tuple(args), cwd))

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    prepared = runner._prepare_go_runner(tmp_path)
    try:
        prepared.run("http://127.0.0.1:12345", "rpc")
        prepared.run("http://127.0.0.1:12345", "binary")
    finally:
        prepared.close()

    build_calls = [call for call in calls if call[0][:2] == ("go", "build")]
    scenario_calls = [call for call in calls if call[0][0] != "go"]
    assert len(build_calls) == 1
    assert [call[0][-2:] for call in scenario_calls] == [
        ("http://127.0.0.1:12345", "rpc"),
        ("http://127.0.0.1:12345", "binary"),
    ]


def test_prepare_flutter_runner_runs_pub_get_once_and_reuses_test_process(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[tuple[str, ...], str | None]] = []

    def fake_run(args: list[str], cwd: Path | None = None, check: bool = False, **kwargs: object) -> None:
        env = kwargs.get("env")
        scenario = env.get("API_BLUEPRINT_SCENARIOS") if isinstance(env, dict) else None
        calls.append((tuple(args), scenario))

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    prepared = runner._prepare_flutter_runner(tmp_path)
    prepared.run("http://127.0.0.1:12345", "sse")
    prepared.run("http://127.0.0.1:12345", "websocket")
    prepared.close()

    assert calls[0] == (("dart", "pub", "get"), None)
    assert calls[1:] == [
        (("dart", "test", "test/conformance_test.dart"), "sse"),
        (("dart", "test", "test/conformance_test.dart"), "websocket"),
    ]


def test_cli_list_reports_servers_clients_and_scenarios(capsys: pytest.CaptureFixture[str]) -> None:
    result = cli.main(["list"])

    assert result == 0
    output = capsys.readouterr().out
    assert "servers:" in output
    assert "- go" in output
    assert "clients:" in output
    assert "- kotlin rpc=yes sse=yes websocket=yes" in output
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
