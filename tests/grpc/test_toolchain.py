from __future__ import annotations

import builtins
from pathlib import Path

import pytest

from api_blueprint.writer.grpc.models import GrpcGenerationJob
from api_blueprint.writer.grpc.toolchain import GrpcToolchain


def test_run_go_builds_expected_protoc_command(monkeypatch, tmp_path):
    source_root = tmp_path / "protos"
    source_root.mkdir()
    out_dir = tmp_path / "out"
    include_dir = tmp_path / "includes"
    include_dir.mkdir()

    job = GrpcGenerationJob(
        name="go.greeter",
        lang="go",
        out_dir=out_dir,
        source_root=source_root,
        import_roots=(include_dir,),
        proto_patterns=("greeterpb/greeter.proto",),
        proto_files=(Path("commonpb/common.proto"), Path("greeterpb/greeter.proto")),
        selection_kind="job",
        layout="source_relative",
        plugin_out=out_dir,
    )

    commands: list[tuple[list[str], Path | None]] = []

    monkeypatch.setattr("api_blueprint.writer.grpc.toolchain.shutil.which", lambda name: f"/usr/bin/{name}")

    def fake_run(command: list[str], cwd: Path | None = None, check: bool = False):
        commands.append((command, cwd))
        assert check is True

    monkeypatch.setattr("api_blueprint.writer.grpc.toolchain.subprocess.run", fake_run)

    GrpcToolchain().run_go(job)

    assert out_dir.is_dir()
    assert commands == [
        (
            [
                "protoc",
                f"-I{source_root}",
                f"-I{include_dir}",
                f"--go_out={out_dir}",
                "--go_opt=paths=source_relative",
                f"--go-grpc_out={out_dir}",
                "--go-grpc_opt=paths=source_relative",
                "commonpb/common.proto",
                "greeterpb/greeter.proto",
            ],
            source_root,
        )
    ]


def test_run_go_builds_target_go_package_protoc_command(monkeypatch, tmp_path):
    source_root = tmp_path / "protos"
    source_root.mkdir()
    module_root = tmp_path / "module-root"
    module_root.mkdir()
    out_dir = module_root / "pb"

    job = GrpcGenerationJob(
        name="go.example",
        lang="go",
        out_dir=out_dir,
        source_root=source_root,
        import_roots=(),
        proto_patterns=("shared/example/api/v1/example.proto",),
        proto_files=(Path("shared/example/api/v1/example.proto"),),
        selection_kind="target",
        layout="go_package",
        plugin_out=module_root,
        module="examplemod",
        module_root=module_root,
        expected_go_package_prefix="examplemod/pb",
    )

    commands: list[tuple[list[str], Path | None]] = []

    monkeypatch.setattr("api_blueprint.writer.grpc.toolchain.shutil.which", lambda name: f"/usr/bin/{name}")

    def fake_run(command: list[str], cwd: Path | None = None, check: bool = False):
        commands.append((command, cwd))
        assert check is True

    monkeypatch.setattr("api_blueprint.writer.grpc.toolchain.subprocess.run", fake_run)

    GrpcToolchain().run_go(job)

    assert out_dir.is_dir()
    assert commands == [
        (
            [
                "protoc",
                f"-I{source_root}",
                f"--go_out={module_root}",
                "--go_opt=paths=import",
                "--go_opt=module=examplemod",
                f"--go-grpc_out={module_root}",
                "--go-grpc_opt=paths=import",
                "--go-grpc_opt=module=examplemod",
                "shared/example/api/v1/example.proto",
            ],
            source_root,
        )
    ]


def test_run_python_builds_expected_grpc_tools_args(monkeypatch, tmp_path):
    source_root = tmp_path / "protos"
    source_root.mkdir()
    out_dir = tmp_path / "out"
    include_dir = tmp_path / "includes"
    include_dir.mkdir()
    wkt_dir = tmp_path / "wkt"
    wkt_dir.mkdir()

    job = GrpcGenerationJob(
        name="python.greeter",
        lang="python",
        out_dir=out_dir,
        source_root=source_root,
        import_roots=(include_dir,),
        proto_patterns=("**/*.proto",),
        proto_files=(Path("commonpb/common.proto"), Path("greeterpb/greeter.proto")),
        selection_kind="target",
        layout="source_relative",
        plugin_out=out_dir,
    )

    captured: list[list[str]] = []

    class FakeProtoc:
        def main(self, args: list[str]) -> int:
            captured.append(args)
            return 0

    toolchain = GrpcToolchain()
    monkeypatch.setattr(toolchain, "load_grpc_tools", lambda: (FakeProtoc(), wkt_dir))

    current = Path.cwd()
    toolchain.run_python(job)

    assert Path.cwd() == current
    assert out_dir.is_dir()
    assert captured == [
        [
            "grpc_tools.protoc",
            f"-I{source_root}",
            f"-I{include_dir}",
            f"-I{wkt_dir}",
            f"--python_out={out_dir}",
            f"--grpc_python_out={out_dir}",
            f"--pyi_out={out_dir}",
            "commonpb/common.proto",
            "greeterpb/greeter.proto",
        ]
    ]


def test_run_python_uses_effective_source_root_as_include_and_cwd(monkeypatch, tmp_path):
    source_root = tmp_path / "protos" / "services" / "exampledomain" / "api"
    source_root.mkdir(parents=True)
    out_dir = tmp_path / "out"
    include_dir = tmp_path / "includes"
    include_dir.mkdir()
    wkt_dir = tmp_path / "wkt"
    wkt_dir.mkdir()

    job = GrpcGenerationJob(
        name="python.services",
        lang="python",
        out_dir=out_dir,
        source_root=source_root,
        import_roots=(include_dir,),
        proto_patterns=("feature/v1/example.proto",),
        proto_files=(Path("feature/v1/example.proto"),),
        selection_kind="target",
        layout="source_relative",
        plugin_out=out_dir,
    )

    captured: list[tuple[list[str], Path]] = []

    class FakeProtoc:
        def main(self, args: list[str]) -> int:
            captured.append((args, Path.cwd()))
            return 0

    toolchain = GrpcToolchain()
    monkeypatch.setattr(toolchain, "load_grpc_tools", lambda: (FakeProtoc(), wkt_dir))

    current = Path.cwd()
    toolchain.run_python(job)

    assert Path.cwd() == current
    assert out_dir.is_dir()
    assert captured == [
        (
            [
                "grpc_tools.protoc",
                f"-I{source_root}",
                f"-I{include_dir}",
                f"-I{wkt_dir}",
                f"--python_out={out_dir}",
                f"--grpc_python_out={out_dir}",
                f"--pyi_out={out_dir}",
                "feature/v1/example.proto",
            ],
            source_root,
        )
    ]


def test_load_grpc_tools_reports_missing_dependency(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name: str, *args, **kwargs):
        if name == "grpc_tools":
            raise ModuleNotFoundError("No module named 'grpc_tools'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ModuleNotFoundError, match="grpcio-tools"):
        GrpcToolchain().load_grpc_tools()
