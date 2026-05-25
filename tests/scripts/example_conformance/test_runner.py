from __future__ import annotations

from .helpers import *


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
    monkeypatch.setattr(runner.server, "start_server", lambda server_name, blueprint, **kwargs: fake_server)
    monkeypatch.setattr(runner.server, "cleanup_server_log", lambda path: None)
    monkeypatch.setattr(runner, "_prepare_client_runner", lambda ws, client: FakePreparedRunner())

    runner._run_against_workspace(
        fake_workspace,  # type: ignore[arg-type]
        server_names=("go",),
        clients=("flutter",),
        selected_scenarios=scenarios.filter_scenarios(("sse", "websocket")),
    )

    captured = capsys.readouterr()
    assert "go:" in captured.out
    assert "  - server/setup ... ok http://127.0.0.1:12345" in captured.out
    assert "flutter:" in captured.out
    assert "    - flutter/setup ... ok" in captured.out
    assert "    - flutter/sse ... ok" in captured.out
    assert "    - flutter/websocket ... ok" in captured.out
    assert "client noisy output" not in captured.out
    assert calls == [("http://127.0.0.1:12345", "sse"), ("http://127.0.0.1:12345", "websocket"), ("closed", "")]

def test_runner_runs_server_safety_scenarios_without_preparing_clients(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_server = SimpleNamespace(
        base_url="http://127.0.0.1:12345",
        output_path=Path(".conformance-server.log"),
        stop=lambda: None,
    )
    fake_workspace = SimpleNamespace(blueprint=SimpleNamespace(golang_server_dir=Path(".")))
    safety_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(runner.server, "start_server", lambda server_name, blueprint, **kwargs: fake_server)
    monkeypatch.setattr(runner.server, "cleanup_server_log", lambda path: None)
    monkeypatch.setattr(
        safety,
        "run_probe",
        lambda base_url, scenario_name: safety_calls.append((base_url, scenario_name)),
    )
    monkeypatch.setattr(
        runner,
        "_prepare_client_runner",
        lambda ws, client: pytest.fail("client runner should not be prepared for server-only safety scenarios"),
    )

    runner._run_against_workspace(
        fake_workspace,  # type: ignore[arg-type]
        server_names=("go",),
        clients=("typescript",),
        selected_scenarios=scenarios.filter_scenarios(("bad-json", "malformed-websocket")),
    )

    captured = capsys.readouterr()
    assert "safety:" in captured.out
    assert "    - safety/bad-json ... ok" in captured.out
    assert "    - safety/malformed-websocket ... ok" in captured.out
    assert safety_calls == [
        ("http://127.0.0.1:12345", "bad-json"),
        ("http://127.0.0.1:12345", "malformed-websocket"),
    ]

def test_runner_filters_server_safety_scenarios_by_server_capability(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_server = SimpleNamespace(
        base_url="http://127.0.0.1:12345",
        output_path=Path(".conformance-server.log"),
        stop=lambda: None,
    )
    fake_workspace = SimpleNamespace(blueprint=SimpleNamespace(golang_server_dir=Path(".")))
    safety_calls: list[str] = []

    monkeypatch.setattr(runner.server, "start_server", lambda server_name, blueprint, **kwargs: fake_server)
    monkeypatch.setattr(runner.server, "cleanup_server_log", lambda path: None)
    monkeypatch.setattr(safety, "run_probe", lambda base_url, scenario_name: safety_calls.append(scenario_name))
    original_server_manifest = manifest.server_manifest
    monkeypatch.setattr(
        manifest,
        "server_manifest",
        lambda: {
            **original_server_manifest(),
            "python": manifest.ServerCapability(
                name="python",
                command_label="Python FastAPI",
                enabled=True,
                planned=True,
                supports_rpc=True,
                supports_binary=False,
                supports_form=True,
                supports_typed_error=True,
                supports_sse=True,
                supports_websocket=True,
                supports_naming=True,
            ),
        },
    )

    runner._run_against_workspace(
        fake_workspace,  # type: ignore[arg-type]
        server_names=("python",),
        clients=("typescript",),
        selected_scenarios=scenarios.filter_scenarios(("bad-binary", "bad-json")),
    )

    captured = capsys.readouterr()
    assert "safety ... skipped no runnable scenarios for server python: bad-binary" in captured.out
    assert "    - safety/bad-json ... ok" in captured.out
    assert safety_calls == ["bad-json"]

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
    monkeypatch.setattr(runner.server, "start_server", lambda server_name, blueprint, **kwargs: fake_server)
    monkeypatch.setattr(runner.server, "cleanup_server_log", lambda path: None)
    monkeypatch.setattr(runner, "_prepare_client_runner", lambda ws, client: FakePreparedRunner(client))

    runner._run_against_workspace(
        fake_workspace,  # type: ignore[arg-type]
        server_names=("go",),
        clients=("typescript", "kotlin"),
        selected_scenarios=scenarios.filter_scenarios(("sse", "websocket")),
    )

    captured = capsys.readouterr()
    assert "typescript:" in captured.out
    assert "    - typescript/setup ... ok" in captured.out
    assert "    - typescript/sse ... ok" in captured.out
    assert "    - typescript/websocket ... ok" in captured.out
    assert "kotlin:" in captured.out
    assert "    - kotlin/setup ... ok" in captured.out
    assert "    - kotlin/sse ... ok" in captured.out
    assert "    - kotlin/websocket ... ok" in captured.out
    assert calls == [
        ("typescript", "http://127.0.0.1:12345", "sse"),
        ("typescript", "http://127.0.0.1:12345", "websocket"),
        ("typescript", "closed", ""),
        ("kotlin", "http://127.0.0.1:12345", "sse"),
        ("kotlin", "http://127.0.0.1:12345", "websocket"),
        ("kotlin", "closed", ""),
    ]

def test_runner_filters_scenarios_by_server_capability(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_server = SimpleNamespace(
        base_url="http://127.0.0.1:12345",
        output_path=Path(".conformance-server.log"),
        stop=lambda: None,
    )
    fake_workspace = SimpleNamespace(blueprint=SimpleNamespace(golang_server_dir=Path(".")))
    calls: list[str] = []

    class FakePreparedRunner:
        def run(self, base_url: str, scenario_arg: str) -> None:
            calls.append(scenario_arg)

        def close(self) -> None:
            calls.append("closed")

    monkeypatch.setattr(runner.server, "start_server", lambda server_name, blueprint, **kwargs: fake_server)
    monkeypatch.setattr(runner.server, "cleanup_server_log", lambda path: None)
    monkeypatch.setattr(runner, "_prepare_client_runner", lambda ws, client: FakePreparedRunner())
    original_server_manifest = manifest.server_manifest
    monkeypatch.setattr(
        manifest,
        "server_manifest",
        lambda: {
            **original_server_manifest(),
            "python": manifest.ServerCapability(
                name="python",
                command_label="Python FastAPI",
                enabled=True,
                planned=True,
                supports_rpc=True,
                supports_binary=False,
                supports_form=True,
                supports_typed_error=True,
                supports_sse=True,
                supports_websocket=True,
                supports_naming=True,
            ),
        },
    )

    runner._run_against_workspace(
        fake_workspace,  # type: ignore[arg-type]
        server_names=("python",),
        clients=("typescript",),
        selected_scenarios=scenarios.filter_scenarios(("binary", "sse")),
    )

    captured = capsys.readouterr()
    assert "typescript ... skipped no runnable scenarios for server python: binary" in captured.out
    assert "    - typescript/sse ... ok" in captured.out
    assert calls == ["sse", "closed"]

def test_runner_prints_summary_once_after_all_servers(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_workspace = SimpleNamespace(blueprint=SimpleNamespace(golang_server_dir=Path(".")))

    class FakePreparedRunner:
        def run(self, base_url: str, scenario_arg: str) -> None:
            return None

        def close(self) -> None:
            return None

    def fake_start_server(server_name: str, blueprint, **kwargs) -> SimpleNamespace:
        return SimpleNamespace(
            base_url=f"http://127.0.0.1/{server_name}",
            output_path=Path(".conformance-server.log"),
            stop=lambda: None,
        )

    monkeypatch.setattr(runner.server, "start_server", fake_start_server)
    monkeypatch.setattr(runner.server, "cleanup_server_log", lambda path: None)
    monkeypatch.setattr(runner, "_prepare_client_runner", lambda ws, client: FakePreparedRunner())

    runner._run_against_workspace(
        fake_workspace,  # type: ignore[arg-type]
        server_names=("go", "python"),
        clients=("typescript",),
        selected_scenarios=scenarios.filter_scenarios(("rpc",)),
    )

    captured = capsys.readouterr()
    assert captured.out.count("conformance passed:") == 1
    assert captured.out.rfind("conformance passed:") > captured.out.rfind("python:")

def test_runner_replays_server_log_when_client_stage_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    log_path = tmp_path / ".conformance-server.log"
    log_path.write_text("server traceback\n", encoding="utf-8")
    fake_server = SimpleNamespace(
        base_url="http://127.0.0.1:12345",
        output_path=log_path,
        stop=lambda: None,
    )
    fake_workspace = SimpleNamespace(blueprint=SimpleNamespace(golang_server_dir=Path(".")))

    class FailingPreparedRunner:
        def run(self, base_url: str, scenario_arg: str) -> None:
            raise RuntimeError("client failed")

        def close(self) -> None:
            return None

    monkeypatch.setattr(runner.server, "start_server", lambda server_name, blueprint, **kwargs: fake_server)
    monkeypatch.setattr(runner.server, "cleanup_server_log", lambda path: None)
    monkeypatch.setattr(runner, "_prepare_client_runner", lambda ws, client: FailingPreparedRunner())

    with pytest.raises(RuntimeError, match="client failed"):
        runner._run_against_workspace(
            fake_workspace,  # type: ignore[arg-type]
            server_names=("python",),
            clients=("typescript",),
            selected_scenarios=scenarios.filter_scenarios(("rpc",)),
        )

    captured = capsys.readouterr()
    assert "--- python server log ---" in captured.err
    assert "server traceback" in captured.err


def test_runner_runs_br_scenario_with_registered_decoder_server_env(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_server = SimpleNamespace(
        base_url="http://127.0.0.1:12345",
        output_path=Path(".conformance-server.log"),
        stop=lambda: None,
    )
    fake_workspace = SimpleNamespace(blueprint=SimpleNamespace(golang_server_dir=Path(".")))
    start_envs: list[dict[str, str]] = []
    calls: list[str] = []

    class FakePreparedRunner:
        def run(self, base_url: str, scenario_arg: str) -> None:
            calls.append(scenario_arg)

        def close(self) -> None:
            calls.append("closed")

    def fake_start_server(server_name: str, blueprint, **kwargs) -> SimpleNamespace:
        start_envs.append(dict(kwargs.get("extra_env") or {}))
        return fake_server

    monkeypatch.setattr(runner.server, "start_server", fake_start_server)
    monkeypatch.setattr(runner.server, "cleanup_server_log", lambda path: None)
    monkeypatch.setattr(runner, "_prepare_client_runner", lambda ws, client: FakePreparedRunner())

    runner._run_against_workspace(
        fake_workspace,  # type: ignore[arg-type]
        server_names=("go",),
        clients=("python",),
        selected_scenarios=scenarios.filter_scenarios(("binary-br",)),
    )

    captured = capsys.readouterr()
    assert "go [br-stub]:" in captured.out
    assert start_envs == [{"API_BLUEPRINT_ENABLE_BR_STUB": "1"}]
    assert calls == ["binary-br", "closed"]
