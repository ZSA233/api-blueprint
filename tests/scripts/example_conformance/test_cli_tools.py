from __future__ import annotations

from .helpers import *
from scripts.example_conformance import workspace as conformance_workspace


def test_parse_csv_filter_accepts_all_keyword() -> None:
    assert manifest.parse_csv_filter("all", {"go", "java"}, label="target") == ("go", "java")
    assert manifest.parse_csv_filter("go,all", {"go", "java"}, label="target") == ("go", "java")

def test_cli_list_reports_servers_clients_and_scenarios(capsys: pytest.CaptureFixture[str]) -> None:
    result = cli.main(["list"])

    assert result == 0
    output = capsys.readouterr().out
    assert "servers:" in output
    assert "- go enabled label=Go HTTP rpc=yes" in output
    assert "- java planned label=Java Spring contract boundary rpc=no" in output
    assert "clients:" in output
    assert "- kotlin rpc=yes sse=yes websocket=yes" in output
    assert "- swift rpc=yes sse=yes websocket=yes binary=yes form=yes connection=native" in output
    assert "- python rpc=yes sse=unsupported-contract websocket=unsupported-contract" in output
    assert "scenarios:" in output
    assert "- binary" in output

def test_cli_run_invokes_runner_with_filters(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[Path, tuple[str, ...], tuple[str, ...], tuple[str, ...], bool, str]] = []

    def fake_run(
        repo_root: Path,
        *,
        servers: tuple[str, ...],
        clients: tuple[str, ...],
        scenario_names: tuple[str, ...],
        keep_workspace: bool,
        swift_runtime_profile: str,
    ) -> None:
        calls.append((repo_root, servers, clients, scenario_names, keep_workspace, swift_runtime_profile))

    monkeypatch.setattr(cli.runner, "run_conformance", fake_run)

    result = cli.main(
        [
            "--repo-root",
            str(tmp_path),
            "run",
            "--servers",
            "go,kotlin",
            "--clients",
            "go,flutter",
            "--scenario",
            "rpc,binary",
            "--swift-runtime-profile",
            "ios14-compat",
            "--keep-workspace",
        ]
    )

    assert result == 0
    assert calls == [
        (tmp_path.resolve(), ("go", "kotlin"), ("go", "flutter"), ("rpc", "binary"), True, "ios14-compat")
    ]

def test_cli_generate_invokes_runner(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[Path, bool]] = []

    def fake_generate(repo_root: Path, *, keep_workspace: bool) -> None:
        calls.append((repo_root, keep_workspace))

    monkeypatch.setattr(cli.runner, "generate_conformance_workspace", fake_generate)

    result = cli.main(["--repo-root", str(tmp_path), "generate", "--keep-workspace"])

    assert result == 0
    assert calls == [(tmp_path.resolve(), True)]


def test_prepare_generated_workspace_overrides_swift_runtime_profile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = tmp_path / "api-blueprint.toml"
    config.write_text(
        """
[[swift.client]]
id = "swift.client"
out_dir = "swift"
package = "ExampleClient"
module = "Example"
runtime_profile = "modern"
""".lstrip(),
        encoding="utf-8",
    )
    fake_workspace = SimpleNamespace(root=tmp_path, config_path=config)
    generated_configs: list[str] = []

    monkeypatch.setattr(
        conformance_workspace.example_validation,
        "prepare_blueprint_workspace",
        lambda repo_root: fake_workspace,
    )
    monkeypatch.setattr(
        conformance_workspace.example_validation,
        "regenerate_blueprint_examples",
        lambda workspace: generated_configs.append(workspace.config_path.read_text(encoding="utf-8")),
    )

    result = conformance_workspace.prepare_generated_workspace(
        tmp_path,
        swift_runtime_profile="ios14-compat",
    )

    assert result.temporary is True
    assert result.root == tmp_path
    assert 'runtime_profile = "ios14-compat"' in generated_configs[0]

def test_cli_check_and_refresh_invoke_runner(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    check_calls: list[tuple[Path, tuple[str, ...], tuple[str, ...], tuple[str, ...], bool, str]] = []
    refresh_calls: list[tuple[Path, tuple[str, ...], tuple[str, ...], tuple[str, ...], str]] = []

    def fake_check(
        repo_root: Path,
        *,
        servers: tuple[str, ...],
        clients: tuple[str, ...],
        scenario_names: tuple[str, ...],
        keep_workspace: bool,
        swift_runtime_profile: str,
    ) -> None:
        check_calls.append((repo_root, servers, clients, scenario_names, keep_workspace, swift_runtime_profile))

    def fake_refresh(
        repo_root: Path,
        *,
        servers: tuple[str, ...],
        clients: tuple[str, ...],
        scenario_names: tuple[str, ...],
        swift_runtime_profile: str,
    ) -> None:
        refresh_calls.append((repo_root, servers, clients, scenario_names, swift_runtime_profile))

    monkeypatch.setattr(cli.runner, "check_conformance", fake_check)
    monkeypatch.setattr(cli.runner, "refresh_and_check", fake_refresh)

    check_result = cli.main(
        [
            "--repo-root",
            str(tmp_path),
            "check",
            "--server",
            "go",
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
            "--servers",
            "go,kotlin",
            "--clients",
            "flutter",
            "--scenario",
            "sse",
            "--swift-runtime-profile",
            "ios14-compat",
        ]
    )

    assert check_result == 0
    assert refresh_result == 0
    assert check_calls == [(tmp_path.resolve(), ("go",), ("typescript", "kotlin"), ("form", "error"), True, "modern")]
    assert refresh_calls == [(tmp_path.resolve(), ("go", "kotlin"), ("flutter",), ("sse",), "ios14-compat")]

def test_cli_rejects_conflicting_server_flags(capsys: pytest.CaptureFixture[str]) -> None:
    result = cli.main(["run", "--server", "go", "--servers", "java"])

    assert result == 1
    assert "use either --server or --servers, not both" in capsys.readouterr().err

def test_tools_reports_missing_language_binaries(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_which(binary: str) -> str | None:
        return None if binary in {"go", "dart", "tsc"} else f"/usr/bin/{binary}"

    monkeypatch.setattr(tools.shutil, "which", fake_which)
    monkeypatch.setattr(tools.example_validation, "resolve_gradle_bin", lambda: None)
    monkeypatch.setattr(tools.example_validation, "resolve_swift_bin", lambda: None)

    missing = tools.missing_tools_for_clients(("go", "typescript", "kotlin", "flutter", "swift", "java", "python"))

    assert "go: required for go conformance" in missing
    assert "tsc: required for typescript conformance" in missing
    assert "gradle: required for kotlin conformance; set API_BLUEPRINT_GRADLE_BIN if needed" in missing
    assert "dart: required for flutter conformance" in missing
    assert "swift: required for swift conformance; set API_BLUEPRINT_SWIFT_BIN if needed" in missing
    assert "gradle: required for java conformance; set API_BLUEPRINT_GRADLE_BIN if needed" in missing
    assert "python: required for python conformance" not in missing

def test_tools_reports_go_binary_required_for_go_server(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tools.shutil, "which", lambda binary: None if binary == "go" else f"/usr/bin/{binary}")

    missing = tools.missing_tools_for_targets("go", ("flutter",))

    assert "go: required for go conformance server" in missing

def test_tools_reports_python_websocket_runtime_for_python_server(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tools.shutil, "which", lambda binary: f"/usr/bin/{binary}")
    monkeypatch.setattr(
        tools.importlib.util,
        "find_spec",
        lambda name: None if name == "websockets" else object(),
    )

    missing = tools.missing_tools_for_targets("python", ("typescript",))

    assert "websockets: required for python conformance server WebSocket support" in missing
