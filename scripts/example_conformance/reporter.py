from __future__ import annotations

import os
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TypeVar

T = TypeVar("T")

GREEN = "32"
RED = "31"
YELLOW = "33"
DIM = "2"


def run_stage(
    label: str,
    action: Callable[[], T],
    *,
    success_detail: Callable[[T], str] | None = None,
) -> T:
    print(f"{label} ... ", end="", flush=True)
    captured_output = ""
    try:
        with _capture_process_output() as read_output:
            try:
                result = action()
            except Exception:
                captured_output = read_output()
                raise
    except Exception:
        print(_paint("failed", RED), flush=True)
        _replay_captured_output(label, captured_output)
        raise

    detail = ""
    if success_detail is not None:
        detail_value = success_detail(result)
        if detail_value:
            detail = f" {detail_value}"
    print(f"{_paint('ok', GREEN)}{detail}", flush=True)
    return result


def print_skipped(label: str, reason: str) -> None:
    print(f"{label} ... {_paint('skipped', YELLOW)} {reason}", flush=True)


def print_group(label: str) -> None:
    print(f"{label}:", flush=True)


def run_sub_stage(label: str, action: Callable[[], T]) -> T:
    return run_stage(f"  - {label}", action)


def print_summary(*, server: str, clients: tuple[str, ...], scenarios: tuple[str, ...]) -> None:
    print(
        f"conformance {_paint('passed', GREEN)}: "
        f"server={server} clients={','.join(clients)} scenarios={','.join(scenarios)}",
        flush=True,
    )


def _replay_captured_output(label: str, output: str) -> None:
    if not output.strip():
        return
    print(f"--- {label} output ---", file=sys.stderr)
    print(output, end="" if output.endswith("\n") else "\n", file=sys.stderr)


def _paint(text: str, color: str) -> str:
    if not _color_enabled():
        return text
    return f"\x1b[{color}m{text}\x1b[0m"


def _color_enabled() -> bool:
    force = os.environ.get("FORCE_COLOR")
    if force and force != "0":
        return True
    if os.environ.get("NO_COLOR"):
        return False
    py_colors = os.environ.get("PY_COLORS")
    if py_colors == "1":
        return True
    if py_colors == "0":
        return False
    return sys.stdout.isatty()


@contextmanager
def _capture_process_output() -> Iterator[Callable[[], str]]:
    saved_stdout = sys.stdout
    saved_stderr = sys.stderr
    stdout_fd = os.dup(1)
    stderr_fd = os.dup(2)
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8", errors="replace") as output:
        try:
            sys.stdout = output
            sys.stderr = output
            os.dup2(output.fileno(), 1)
            os.dup2(output.fileno(), 2)

            def read_output() -> str:
                output.flush()
                output.seek(0)
                return output.read()

            yield read_output
        finally:
            output.flush()
            os.dup2(stdout_fd, 1)
            os.dup2(stderr_fd, 2)
            os.close(stdout_fd)
            os.close(stderr_fd)
            sys.stdout = saved_stdout
            sys.stderr = saved_stderr
