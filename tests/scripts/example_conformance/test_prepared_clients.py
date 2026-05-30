from __future__ import annotations

from .helpers import *


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

def test_prepare_swift_runner_builds_once_and_reuses_executable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    swift_dir = tmp_path / "swift"
    conformance_dir = swift_dir / "Conformance"
    conformance_dir.mkdir(parents=True)
    (conformance_dir / "Package.swift").write_text(
        "// swift-tools-version: 5.9\n",
        encoding="utf-8",
    )
    calls: list[tuple[tuple[str, ...], Path | None]] = []

    def fake_run(args: list[str], cwd: Path | None = None, check: bool = False, **kwargs: object) -> None:
        calls.append((tuple(args), cwd))
        if args[:3] == ["/usr/bin/swift", "build", "-c"]:
            executable = conformance_dir / ".build" / "release" / "SwiftConformance"
            executable.parent.mkdir(parents=True, exist_ok=True)
            executable.write_text("#!/bin/sh\n", encoding="utf-8")

    monkeypatch.setattr(runner.example_validation, "resolve_swift_bin", lambda: "/usr/bin/swift")
    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    prepared = runner._prepare_swift_runner(swift_dir)
    try:
        prepared.run("http://127.0.0.1:12345", "sse")
        prepared.run("http://127.0.0.1:12345", "websocket")
    finally:
        prepared.close()

    build_calls = [call for call in calls if call[0][:2] == ("/usr/bin/swift", "build")]
    scenario_calls = [call for call in calls if call[0][0] != "/usr/bin/swift"]
    assert len(build_calls) == 1
    assert [call[0][-2:] for call in scenario_calls] == [
        ("http://127.0.0.1:12345", "sse"),
        ("http://127.0.0.1:12345", "websocket"),
    ]

def test_prepare_java_runner_builds_once_and_reuses_executable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    java_client_dir = tmp_path / "java" / "client"
    conformance_dir = tmp_path / "java" / "conformance"
    conformance_dir.mkdir(parents=True)
    (conformance_dir / "Conformance.java").write_text(
        "package com.example.apiblueprint.conformance; public final class Conformance {}\n",
        encoding="utf-8",
    )
    (java_client_dir / "com").mkdir(parents=True)
    calls: list[tuple[tuple[str, ...], Path | None]] = []

    def fake_run(args: list[str], cwd: Path | None = None, check: bool = False, **kwargs: object) -> None:
        calls.append((tuple(args), cwd))
        if args[-1] == "installDist":
            executable = (
                cwd
                / "build"
                / "install"
                / "api-blueprint-java-conformance"
                / "bin"
                / ("api-blueprint-java-conformance.bat" if runner.os.name == "nt" else "api-blueprint-java-conformance")
            )
            executable.parent.mkdir(parents=True, exist_ok=True)
            executable.write_text("#!/bin/sh\n", encoding="utf-8")

    monkeypatch.setattr(runner.example_validation, "resolve_gradle_bin", lambda: "gradle")
    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    prepared = runner._prepare_java_runner(java_client_dir, conformance_dir)
    try:
        prepared.run("http://127.0.0.1:12345", "rpc")
        prepared.run("http://127.0.0.1:12345", "binary")
    finally:
        prepared.close()

    build_calls = [call for call in calls if call[0][-1] == "installDist"]
    scenario_calls = [call for call in calls if call[0][0] != "gradle"]
    assert len(build_calls) == 1
    assert [call[0][-2:] for call in scenario_calls] == [
        ("http://127.0.0.1:12345", "rpc"),
        ("http://127.0.0.1:12345", "binary"),
    ]

def test_prepare_python_runner_reuses_preserved_script(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    python_dir = tmp_path / "python"
    conformance_dir = python_dir / "conformance"
    conformance_dir.mkdir(parents=True)
    (conformance_dir / "client.py").write_text("print('client')\n", encoding="utf-8")
    calls: list[tuple[tuple[str, ...], Path | None]] = []

    def fake_run(args: list[str], cwd: Path | None = None, check: bool = False, **kwargs: object) -> None:
        calls.append((tuple(args), cwd))

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    prepared = runner._prepare_python_runner(python_dir)
    prepared.run("http://127.0.0.1:12345", "rpc")
    prepared.run("http://127.0.0.1:12345", "sse")
    prepared.close()

    assert [call[0][-2:] for call in calls] == [
        ("http://127.0.0.1:12345", "rpc"),
        ("http://127.0.0.1:12345", "sse"),
    ]
    assert all(call[1] == python_dir for call in calls)
