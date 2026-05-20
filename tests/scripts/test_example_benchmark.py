from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.example_benchmark import protocol


def test_example_benchmark_help_and_list() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    help_result = subprocess.run(
        [sys.executable, "-m", "scripts.example_benchmark", "--help"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert help_result.returncode == 0, help_result.stdout + help_result.stderr
    help_text = help_result.stdout + help_result.stderr
    assert "list" in help_text
    assert "binary" in help_text
    assert "protocol" in help_text

    list_result = subprocess.run(
        [sys.executable, "-m", "scripts.example_benchmark", "list"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert list_result.returncode == 0, list_result.stdout + list_result.stderr
    assert "binary targets:" in list_result.stdout
    assert "- go" in list_result.stdout
    assert "protocol servers:" in list_result.stdout
    assert "protocol scenarios:" in list_result.stdout


def test_example_benchmark_protocol_rejects_unknown_filter() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.example_benchmark",
            "protocol",
            "--servers",
            "missing",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "unknown conformance server: missing" in result.stderr


def test_protocol_benchmark_suppresses_setup_noise(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_workspace = SimpleNamespace(root=tmp_path, temporary=False, blueprint=SimpleNamespace())
    fake_server = SimpleNamespace(
        base_url="http://127.0.0.1:1",
        output_path=tmp_path / "server.log",
        stop=lambda: None,
    )

    def noisy_workspace(repo_root: Path) -> SimpleNamespace:
        print("noisy generation")
        return fake_workspace

    def noisy_server(server_name: str, blueprint: object) -> SimpleNamespace:
        print("noisy server setup")
        return fake_server

    monkeypatch.setattr(protocol.workspace, "prepare_generated_workspace", noisy_workspace)
    monkeypatch.setattr(protocol.server, "start_server", noisy_server)
    monkeypatch.setattr(protocol.server, "cleanup_server_log", lambda path: None)
    monkeypatch.setattr(protocol, "_selected_scenarios", lambda scenario_names: ())
    monkeypatch.setattr(protocol.tools, "ensure_tools_for_targets", lambda servers, clients: None)

    asyncio.run(
        protocol.run_protocol_benchmark(
            protocol.ProtocolBenchmarkOptions(
                repo_root=tmp_path,
                servers=("python",),
                scenario_names=("rpc-json",),
                requests=1,
                concurrency=1,
                warmup=0,
                keep_workspace=False,
            )
        )
    )

    captured = capsys.readouterr()
    assert "noisy generation" not in captured.out
    assert "noisy server setup" not in captured.out
