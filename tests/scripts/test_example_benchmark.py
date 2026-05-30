from __future__ import annotations

import asyncio
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.example_benchmark import binary, cli, protocol


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
    assert "- swift" in list_result.stdout
    assert "protocol servers:" in list_result.stdout
    assert "protocol scenarios:" in list_result.stdout
    assert "sdk smoke scenarios:" in list_result.stdout


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


def test_example_benchmark_sdk_smoke_delegates_to_conformance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, object]] = []

    def fake_run_conformance(
        repo_root: Path,
        *,
        servers: tuple[str, ...],
        clients: tuple[str, ...],
        scenario_names: tuple[str, ...],
        keep_workspace: bool,
    ) -> None:
        calls.append(
            {
                "repo_root": repo_root,
                "servers": servers,
                "clients": clients,
                "scenario_names": scenario_names,
                "keep_workspace": keep_workspace,
            }
        )

    monkeypatch.setattr(cli.runner, "run_conformance", fake_run_conformance)

    result = cli.main(
        [
            "--repo-root",
            str(tmp_path),
            "sdk-smoke",
            "--servers",
            "go",
            "--clients",
            "python",
            "--scenario",
            "request-options,binary-response,media",
        ]
    )

    assert result == 0
    assert calls == [
        {
            "repo_root": tmp_path.resolve(),
            "servers": ("go",),
            "clients": ("python",),
            "scenario_names": ("request-options", "binary-response", "media"),
            "keep_workspace": False,
        }
    ]


def test_example_benchmark_binary_java_smoke_uses_fake_runner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[binary.BenchmarkContext] = []

    def fake_java(ctx: binary.BenchmarkContext) -> binary.BenchmarkResult:
        calls.append(ctx)
        return binary.BenchmarkResult(target="java", returncode=0)

    monkeypatch.setitem(binary.RUNNERS, "java", fake_java)

    result = cli.main(["--repo-root", str(tmp_path), "binary", "--target", "java", "--count", "1"])

    assert result == 0
    assert len(calls) == 1
    assert calls[0].repo_root == tmp_path.resolve()
    assert calls[0].count == 1
    assert calls[0].compare_head is False


def test_example_benchmark_binary_all_smoke_uses_fake_runners(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    def make_runner(target: str) -> Callable[[binary.BenchmarkContext], binary.BenchmarkResult]:
        def fake_runner(ctx: binary.BenchmarkContext) -> binary.BenchmarkResult:
            assert ctx.repo_root == tmp_path.resolve()
            assert ctx.count == 1
            calls.append(target)
            return binary.BenchmarkResult(target=target, returncode=0)

        return fake_runner

    for target in binary.TARGETS:
        monkeypatch.setitem(binary.RUNNERS, target, make_runner(target))

    result = cli.main(["--repo-root", str(tmp_path), "binary", "--target", "all", "--count", "1"])

    assert result == 0
    assert calls == list(binary.TARGETS)


def test_java_binary_benchmark_uses_generated_names_with_fake_subprocess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    commands: list[list[str]] = []
    compiled_sources: set[str] = set()
    benchmark_source = ""

    monkeypatch.setattr(binary, "_require_tool", lambda tool: True)

    def fake_run(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        nonlocal benchmark_source
        commands.append(command)
        if command[0] == "javac":
            source_root = cwd / "src"
            api_root = source_root / "com" / "example" / "apiblueprint" / "api"
            route_dir = api_root / "routes" / "api" / "binary"
            runtime_dir = api_root / "runtime"
            benchmark_source = (source_root / "tmpbench" / "JavaBinaryBenchmark.java").read_text(
                encoding="utf-8"
            )
            compiled_sources.update(Path(source).name for source in command if source.endswith(".java"))

            assert (route_dir / "GenBinaryTypes.java").is_file()
            assert not (route_dir / "BinaryTypes.java").exists()
            assert (runtime_dir / "GenApiTypes.java").is_file()
            assert (runtime_dir / "GenApiFilePart.java").is_file()
            assert not (runtime_dir / "ApiTypes.java").exists()
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="iterations=1\n",
            stderr="",
        )

    monkeypatch.setattr(binary, "_run", fake_run)

    result = binary.run_java(
        binary.BenchmarkContext(repo_root=repo_root, count=1, env={}, compare_head=False)
    )

    assert result == binary.BenchmarkResult(target="java", returncode=0)
    assert [command[0] for command in commands] == ["javac", "java"]
    assert "GenApiBinaryBody.java" in compiled_sources
    assert "GenBinaryRuntime.java" in compiled_sources
    assert "GenBinaryTypes.java" in compiled_sources
    assert "ApiBinaryBody.java" not in compiled_sources
    assert "BinaryTypes.java" not in compiled_sources
    assert "ApiTypes.java" not in compiled_sources
    assert "runtime.binary.GenApiBinaryBody" in benchmark_source
    assert "routes.api.binary.GenBinaryTypes" in benchmark_source
    assert "runtime.binary.ApiBinaryBody" not in benchmark_source
    assert "routes.api.binary.BinaryTypes" not in benchmark_source


def test_swift_binary_benchmark_uses_swift_package_product_with_fake_subprocess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    commands: list[list[str]] = []
    package_source = ""
    benchmark_source = ""

    monkeypatch.setattr(binary, "_require_tool", lambda tool: True)

    def fake_run(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        nonlocal package_source, benchmark_source
        commands.append(command)
        package_source = (cwd / "Package.swift").read_text(encoding="utf-8")
        benchmark_source = (cwd / "Sources" / "SwiftBinaryBenchmark" / "main.swift").read_text(encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="iterations=1\n", stderr="")

    monkeypatch.setattr(binary, "_run", fake_run)

    result = binary.run_swift(
        binary.BenchmarkContext(repo_root=repo_root, count=1, env={}, compare_head=False)
    )

    assert result == binary.BenchmarkResult(target="swift", returncode=0)
    assert commands == [["swift", "run", "-c", "release", "SwiftBinaryBenchmark", "1"]]
    assert '.product(name: "ABClientAPIRoutes", package: "swift")' in package_source
    assert "import ABClientAPIRoutes" in benchmark_source
    assert "encodeDemoPacket(packet)" in benchmark_source
    assert "decodeDemoPacket(data)" in benchmark_source


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
