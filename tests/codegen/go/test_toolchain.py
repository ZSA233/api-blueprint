from __future__ import annotations

import logging
import subprocess
from pathlib import Path

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


def test_read_gomodule_falls_back_to_go_mod_when_go_is_missing(monkeypatch, tmp_path):
    module_dir = tmp_path / "module"
    output_dir = module_dir / "generated"
    output_dir.mkdir(parents=True)
    (module_dir / "go.mod").write_text("module example.com/generated\n\ngo 1.23\n", encoding="utf-8")

    def fake_run(*args, **kwargs):
        raise FileNotFoundError("go")

    monkeypatch.setattr("api_blueprint.writer.golang.toolchain.subprocess.run", fake_run)

    assert GolangToolchain.read_gomodule(output_dir) == [("example.com/generated", str(module_dir.resolve()))]


def test_resolve_module_import_turns_command_line_arguments_into_module_not_found(monkeypatch, tmp_path):
    monkeypatch.setattr(
        GolangToolchain,
        "read_gomodule",
        staticmethod(lambda _path: [("command-line-arguments", "")]),
    )

    toolchain = GolangToolchain(logging.getLogger("test-golang-toolchain"))
    with pytest.raises(ModuleNotFoundError, match="找不到 gomodule"):
        toolchain.resolve_module_import(tmp_path, label="[wails]")


def test_resolve_module_import_normalizes_real_paths(monkeypatch, tmp_path):
    real_root = tmp_path / "real"
    real_root.mkdir()
    link_root = tmp_path / "link"
    link_root.symlink_to(real_root, target_is_directory=True)

    monkeypatch.setattr(
        GolangToolchain,
        "read_gomodule",
        staticmethod(lambda _path: [("example.com/demo", str(real_root.resolve()))]),
    )

    toolchain = GolangToolchain(logging.getLogger("test-golang-toolchain"))
    resolved = toolchain.resolve_module_import(Path(link_root), module="example.com/demo", label="[go]")

    assert resolved.module == "example.com/demo"
    assert resolved.import_path == "example.com/demo"
