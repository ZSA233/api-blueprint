from __future__ import annotations

import logging
import subprocess

import pytest

from api_blueprint.writer.golang.toolchain import GolangToolchain


def test_read_gomodule_preserves_empty_dir_column(monkeypatch, tmp_path):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="command-line-arguments \n",
            stderr="",
        )

    monkeypatch.setattr("api_blueprint.writer.golang.toolchain.subprocess.run", fake_run)

    assert GolangToolchain.read_gomodule(tmp_path) == [("command-line-arguments", "")]


def test_resolve_module_import_turns_command_line_arguments_into_module_not_found(monkeypatch, tmp_path):
    monkeypatch.setattr(
        GolangToolchain,
        "read_gomodule",
        staticmethod(lambda _path: [("command-line-arguments", "")]),
    )

    toolchain = GolangToolchain(logging.getLogger("test-golang-toolchain"))
    with pytest.raises(ModuleNotFoundError, match="找不到 gomodule"):
        toolchain.resolve_module_import(tmp_path, label="[wails]")
