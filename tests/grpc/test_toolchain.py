from __future__ import annotations

import builtins
from pathlib import Path

import pytest

from api_blueprint.writer.grpc.models import GrpcGenerationJob
from api_blueprint.writer.grpc.toolchain import GrpcToolchain


def test_run_go_builds_expected_protoc_command(monkeypatch, tmp_path):
    proto_root = tmp_path / "protos"
    proto_root.mkdir()
    output = tmp_path / "out"
    include_dir = tmp_path / "includes"
    include_dir.mkdir()

    job = GrpcGenerationJob(
        name="go.greeter",
        preset="go",
        output=output,
        proto_root=proto_root,
        include_paths=(include_dir,),
        proto_patterns=("greeterpb/greeter.proto",),
        proto_files=(Path("commonpb/common.proto"), Path("greeterpb/greeter.proto")),
        layout="source_relative",
    )

    commands: list[tuple[list[str], Path | None]] = []

    monkeypatch.setattr("api_blueprint.writer.grpc.toolchain.shutil.which", lambda name: f"/usr/bin/{name}")

    def fake_run(command: list[str], cwd: Path | None = None, check: bool = False):
        commands.append((command, cwd))
        assert check is True

    monkeypatch.setattr("api_blueprint.writer.grpc.toolchain.subprocess.run", fake_run)

    GrpcToolchain().run_go(job)

    assert output.is_dir()
    assert commands == [
        (
            [
                "protoc",
                f"-I{proto_root}",
                f"-I{include_dir}",
                f"--go_out={output}",
                "--go_opt=paths=source_relative",
                f"--go-grpc_out={output}",
                "--go-grpc_opt=paths=source_relative",
                "commonpb/common.proto",
                "greeterpb/greeter.proto",
            ],
            proto_root,
        )
    ]


def test_run_go_builds_go_package_protoc_command(monkeypatch, tmp_path):
    proto_root = tmp_path / "protos"
    proto_root.mkdir()
    output = tmp_path / "module-root"

    job = GrpcGenerationJob(
        name="go.example",
        preset="go",
        output=output,
        proto_root=proto_root,
        include_paths=(),
        proto_patterns=("shared/example/api/v1/example.proto",),
        proto_files=(Path("shared/example/api/v1/example.proto"),),
        layout="go_package",
        module="examplemod",
    )

    commands: list[tuple[list[str], Path | None]] = []

    monkeypatch.setattr("api_blueprint.writer.grpc.toolchain.shutil.which", lambda name: f"/usr/bin/{name}")

    def fake_run(command: list[str], cwd: Path | None = None, check: bool = False):
        commands.append((command, cwd))
        assert check is True

    monkeypatch.setattr("api_blueprint.writer.grpc.toolchain.subprocess.run", fake_run)

    GrpcToolchain().run_go(job)

    assert output.is_dir()
    assert commands == [
        (
            [
                "protoc",
                f"-I{proto_root}",
                f"--go_out={output}",
                "--go_opt=paths=import",
                "--go_opt=module=examplemod",
                f"--go-grpc_out={output}",
                "--go-grpc_opt=paths=import",
                "--go-grpc_opt=module=examplemod",
                "shared/example/api/v1/example.proto",
            ],
            proto_root,
        )
    ]


def test_run_python_builds_expected_grpc_tools_args(monkeypatch, tmp_path):
    proto_root = tmp_path / "protos"
    proto_root.mkdir()
    output = tmp_path / "out"
    include_dir = tmp_path / "includes"
    include_dir.mkdir()
    wkt_dir = tmp_path / "wkt"
    wkt_dir.mkdir()

    job = GrpcGenerationJob(
        name="python.greeter",
        preset="python",
        output=output,
        proto_root=proto_root,
        include_paths=(include_dir,),
        proto_patterns=("**/*.proto",),
        proto_files=(Path("commonpb/common.proto"), Path("greeterpb/greeter.proto")),
        layout="source_relative",
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
    assert output.is_dir()
    assert captured == [
        [
            "grpc_tools.protoc",
            f"-I{proto_root}",
            f"-I{include_dir}",
            f"-I{wkt_dir}",
            f"--python_out={output}",
            f"--grpc_python_out={output}",
            f"--pyi_out={output}",
            "commonpb/common.proto",
            "greeterpb/greeter.proto",
        ]
    ]


def test_run_python_uses_effective_job_proto_root_as_include_and_cwd(monkeypatch, tmp_path):
    proto_root = tmp_path / "protos" / "services" / "exampledomain" / "api"
    proto_root.mkdir(parents=True)
    output = tmp_path / "out"
    include_dir = tmp_path / "includes"
    include_dir.mkdir()
    wkt_dir = tmp_path / "wkt"
    wkt_dir.mkdir()

    job = GrpcGenerationJob(
        name="python.services",
        preset="python",
        output=output,
        proto_root=proto_root,
        include_paths=(include_dir,),
        proto_patterns=("feature/v1/example.proto",),
        proto_files=(Path("feature/v1/example.proto"),),
        layout="source_relative",
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
    assert output.is_dir()
    assert captured == [
        (
            [
                "grpc_tools.protoc",
                f"-I{proto_root}",
                f"-I{include_dir}",
                f"-I{wkt_dir}",
                f"--python_out={output}",
                f"--grpc_python_out={output}",
                f"--pyi_out={output}",
                "feature/v1/example.proto",
            ],
            proto_root,
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
