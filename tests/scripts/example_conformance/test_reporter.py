from __future__ import annotations

from .helpers import *


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
