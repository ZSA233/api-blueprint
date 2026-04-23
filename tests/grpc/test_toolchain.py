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


def test_run_python_with_package_root_builds_virtual_include_and_stages_local_imports(monkeypatch, tmp_path):
    source_root = tmp_path / "protos"
    source_root.mkdir()
    include_dir = tmp_path / "includes"
    (include_dir / "commonpb").mkdir(parents=True)
    (include_dir / "shared").mkdir(parents=True)
    out_dir = tmp_path / "out"
    wkt_dir = tmp_path / "wkt"
    wkt_dir.mkdir()

    (source_root / "greeterpb").mkdir()
    (source_root / "greeterpb" / "greeter.proto").write_text(
        """
syntax = "proto3";
import "commonpb/common.proto";
import public "shared/public.proto";
import "google/protobuf/timestamp.proto";
message Greeting {
  google.protobuf.Timestamp ts = 1;
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (include_dir / "commonpb" / "common.proto").write_text(
        """
syntax = "proto3";
message Common {}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (include_dir / "shared" / "public.proto").write_text(
        """
syntax = "proto3";
import weak "shared/weak.proto";
message Public {}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (include_dir / "shared" / "weak.proto").write_text(
        """
syntax = "proto3";
message Weak {}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    job = GrpcGenerationJob(
        name="python.greeter",
        lang="python",
        out_dir=out_dir,
        source_root=source_root,
        import_roots=(include_dir,),
        proto_patterns=("greeterpb/greeter.proto",),
        proto_files=(Path("greeterpb/greeter.proto"),),
        selection_kind="target",
        layout="source_relative",
        plugin_out=out_dir,
        python_package_root="examplegrpc_pb",
        python_package_root_path=Path("examplegrpc_pb"),
    )

    captured: list[tuple[list[str], Path, dict[str, str]]] = []

    class FakeProtoc:
        def main(self, args: list[str]) -> int:
            shadow_root = Path.cwd()
            captured.append(
                (
                    args,
                    shadow_root,
                    {
                        "greeter": (shadow_root / "greeterpb" / "greeter.proto").read_text(encoding="utf-8"),
                        "common": (shadow_root / "commonpb" / "common.proto").read_text(encoding="utf-8"),
                        "public": (shadow_root / "shared" / "public.proto").read_text(encoding="utf-8"),
                        "weak": (shadow_root / "shared" / "weak.proto").read_text(encoding="utf-8"),
                    },
                )
            )
            return 0

    toolchain = GrpcToolchain()
    monkeypatch.setattr(toolchain, "load_grpc_tools", lambda: (FakeProtoc(), wkt_dir))

    current = Path.cwd()
    toolchain.run_python(job)

    assert Path.cwd() == current
    assert out_dir.is_dir()
    assert len(captured) == 1

    args, shadow_root, staged = captured[0]
    assert args[0] == "grpc_tools.protoc"
    assert args[1].startswith("-Iexamplegrpc_pb=")
    assert Path(args[1].split("=", 1)[1]).resolve() == shadow_root.resolve()
    assert args[2:] == [
        f"-I{wkt_dir}",
        f"--python_out={out_dir}",
        f"--grpc_python_out={out_dir}",
        f"--pyi_out={out_dir}",
        "examplegrpc_pb/greeterpb/greeter.proto",
    ]
    assert 'import "examplegrpc_pb/commonpb/common.proto";' in staged["greeter"]
    assert 'import public "examplegrpc_pb/shared/public.proto";' in staged["greeter"]
    assert 'import "google/protobuf/timestamp.proto";' in staged["greeter"]
    assert 'import weak "examplegrpc_pb/shared/weak.proto";' in staged["public"]
    assert staged["common"].startswith('syntax = "proto3";')
    assert staged["weak"].startswith('syntax = "proto3";')


def test_run_python_with_package_root_generates_prefixed_python_imports(tmp_path):
    source_root = tmp_path / "protos"
    (source_root / "commonpb").mkdir(parents=True)
    (source_root / "greeterpb").mkdir(parents=True)
    out_dir = tmp_path / "out"

    (source_root / "commonpb" / "common.proto").write_text(
        """
syntax = "proto3";
message HelloRequest {
  string name = 1;
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (source_root / "greeterpb" / "greeter.proto").write_text(
        """
syntax = "proto3";
import "commonpb/common.proto";
service Greeter {
  rpc SayHello(HelloRequest) returns (HelloRequest);
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    job = GrpcGenerationJob(
        name="python.greeter",
        lang="python",
        out_dir=out_dir,
        source_root=source_root,
        import_roots=(),
        proto_patterns=("commonpb/common.proto", "greeterpb/greeter.proto"),
        proto_files=(Path("commonpb/common.proto"), Path("greeterpb/greeter.proto")),
        selection_kind="target",
        layout="source_relative",
        plugin_out=out_dir,
        python_package_root="examplegrpc_pb",
        python_package_root_path=Path("examplegrpc_pb"),
    )

    GrpcToolchain().run_python(job)

    greeter_pb2 = out_dir / "examplegrpc_pb" / "greeterpb" / "greeter_pb2.py"
    greeter_pyi = out_dir / "examplegrpc_pb" / "greeterpb" / "greeter_pb2.pyi"
    greeter_pb2_grpc = out_dir / "examplegrpc_pb" / "greeterpb" / "greeter_pb2_grpc.py"

    assert greeter_pb2.is_file()
    assert greeter_pyi.is_file()
    assert greeter_pb2_grpc.is_file()
    assert "from examplegrpc_pb.commonpb import common_pb2 as" in greeter_pb2.read_text(encoding="utf-8")
    assert "from examplegrpc_pb.commonpb import common_pb2 as" in greeter_pyi.read_text(encoding="utf-8")
    assert "from examplegrpc_pb.commonpb import common_pb2 as" in greeter_pb2_grpc.read_text(encoding="utf-8")


def test_load_grpc_tools_reports_missing_dependency(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name: str, *args, **kwargs):
        if name == "grpc_tools":
            raise ModuleNotFoundError("No module named 'grpc_tools'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ModuleNotFoundError, match="grpcio-tools"):
        GrpcToolchain().load_grpc_tools()
