from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from api_blueprint.config import ResolvedApiTargetConfig
from api_blueprint.writer.grpc.toolchain import (
    generate_go_stubs,
    generate_python_stubs,
    select_proto_files,
)


def _target(
    *,
    kind: str,
    out_dir: Path,
    module: str | None = None,
    files: tuple[str, ...] = ("api/**/*.proto",),
    source_root: Path | None = None,
    import_roots: tuple[Path, ...] = (),
    python_package_root: str | None = None,
) -> ResolvedApiTargetConfig:
    return ResolvedApiTargetConfig(
        id=kind,
        kind=kind,  # type: ignore[arg-type]
        out_dir=out_dir,
        module=module,
        proto="grpc.proto",
        source_root=source_root,
        files=files,
        import_roots=import_roots,
        python_package_root=python_package_root,
    )


def test_select_proto_files_returns_sorted_relative_matches(tmp_path: Path) -> None:
    proto_root = tmp_path / "protos"
    (proto_root / "api").mkdir(parents=True)
    (proto_root / "api" / "b.proto").write_text('syntax = "proto3";\n', encoding="utf-8")
    (proto_root / "api" / "a.proto").write_text('syntax = "proto3";\n', encoding="utf-8")

    assert select_proto_files(proto_root, ("api/**/*.proto",)) == (
        Path("api/a.proto"),
        Path("api/b.proto"),
    )


def test_grpc_go_toolchain_runs_protoc_with_selected_proto_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    proto_root = tmp_path / "protos"
    (proto_root / "api").mkdir(parents=True)
    (proto_root / "api" / "demo.proto").write_text('syntax = "proto3";\n', encoding="utf-8")
    import_root = tmp_path / "third_party"
    target = _target(kind="grpc-go", out_dir=tmp_path / "go", import_roots=(import_root,))
    captured: dict[str, Any] = {}

    monkeypatch.setattr("shutil.which", lambda name: f"/usr/local/bin/{name}")

    def fake_run(command: list[str], *, cwd: Path, check: bool) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["cwd"] = cwd
        captured["check"] = check
        return subprocess.CompletedProcess(command, 0)

    generate_go_stubs(proto_root, target, runner=fake_run)

    assert captured["cwd"] == proto_root
    assert captured["check"] is True
    command = captured["command"]
    assert command[:2] == ["protoc", f"-I{proto_root.as_posix()}"]
    assert f"-I{import_root.as_posix()}" in command
    assert f"--go_out={target.out_dir.as_posix()}" in command
    assert "--go_opt=paths=source_relative" in command
    assert f"--go-grpc_out={target.out_dir.as_posix()}" in command
    assert "--go-grpc_opt=paths=source_relative" in command
    assert command[-1] == "api/demo.proto"


def test_grpc_go_toolchain_uses_target_source_root_for_file_selection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    proto_root = tmp_path / "protos"
    source_root = proto_root / "services" / "steamagent" / "browser"
    (source_root / "steam" / "v1").mkdir(parents=True)
    (source_root / "steam" / "v1" / "steam.proto").write_text('syntax = "proto3";\n', encoding="utf-8")
    target = _target(
        kind="grpc-go",
        out_dir=tmp_path / "go",
        source_root=source_root,
        files=("steam/v1/*.proto",),
    )
    captured: dict[str, Any] = {}

    monkeypatch.setattr("shutil.which", lambda name: f"/usr/local/bin/{name}")

    def fake_run(command: list[str], *, cwd: Path, check: bool) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["cwd"] = cwd
        captured["check"] = check
        return subprocess.CompletedProcess(command, 0)

    generate_go_stubs(proto_root, target, runner=fake_run)

    assert captured["cwd"] == source_root
    command = captured["command"]
    assert command[:3] == ["protoc", f"-I{source_root.as_posix()}", f"-I{proto_root.as_posix()}"]
    assert command[-1] == "steam/v1/steam.proto"


def test_grpc_go_toolchain_uses_module_import_paths_when_module_is_configured(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    proto_root = tmp_path / "protos"
    (proto_root / "api").mkdir(parents=True)
    (proto_root / "api" / "demo.proto").write_text('syntax = "proto3";\n', encoding="utf-8")
    target = _target(
        kind="grpc-go",
        out_dir=tmp_path / "go",
        module="example.com/project/grpc/go",
        files=("api/*.proto",),
    )
    captured: dict[str, Any] = {}

    monkeypatch.setattr("shutil.which", lambda name: f"/usr/local/bin/{name}")

    def fake_run(command: list[str], *, cwd: Path, check: bool) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["cwd"] = cwd
        captured["check"] = check
        return subprocess.CompletedProcess(command, 0)

    generate_go_stubs(proto_root, target, runner=fake_run)

    command = captured["command"]
    assert f"--go_opt=module={target.module}" in command
    assert f"--go-grpc_opt=module={target.module}" in command
    assert "--go_opt=paths=source_relative" not in command
    assert "--go-grpc_opt=paths=source_relative" not in command


def test_grpc_python_toolchain_uses_package_root_and_rewrites_generated_imports(tmp_path: Path) -> None:
    proto_root = tmp_path / "protos"
    (proto_root / "api").mkdir(parents=True)
    (proto_root / "api" / "demo.proto").write_text('syntax = "proto3";\n', encoding="utf-8")
    target = _target(kind="grpc-python", out_dir=tmp_path / "python", python_package_root="generated.pb")
    captured: dict[str, Any] = {}

    def fake_protoc_main(args: list[str]) -> int:
        captured["args"] = args
        output_root = Path(next(arg.removeprefix("--python_out=") for arg in args if arg.startswith("--python_out=")))
        (output_root / "api").mkdir(parents=True)
        (output_root / "api" / "demo_pb2_grpc.py").write_text(
            "from api import demo_pb2 as api_dot_demo__pb2\n",
            encoding="utf-8",
        )
        return 0

    generate_python_stubs(
        proto_root,
        target,
        protoc_main=fake_protoc_main,
        builtin_proto_root=tmp_path / "grpc_tools" / "_proto",
    )

    args = captured["args"]
    package_root = target.out_dir / "generated" / "pb"
    assert f"-I{proto_root.as_posix()}" in args
    assert f"--python_out={package_root.as_posix()}" in args
    assert f"--grpc_python_out={package_root.as_posix()}" in args
    assert f"--pyi_out={package_root.as_posix()}" in args
    assert args[-1] == "api/demo.proto"
    assert (target.out_dir / "generated" / "__init__.py").is_file()
    assert (package_root / "__init__.py").is_file()
    assert (package_root / "api" / "__init__.py").is_file()
    assert (package_root / "api" / "demo_pb2_grpc.py").read_text(encoding="utf-8") == (
        "from generated.pb.api import demo_pb2 as api_dot_demo__pb2\n"
    )


def test_grpc_stub_toolchain_rejects_empty_file_selection(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="no proto files matched"):
        select_proto_files(tmp_path / "protos", ("api/**/*.proto",))
