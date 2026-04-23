from __future__ import annotations

from pathlib import Path

import pytest

from api_blueprint.config import ResolvedGrpcJobConfig, ResolvedGrpcTargetConfig
from api_blueprint.writer.grpc.planner import expand_job, expand_target
from api_blueprint.writer.grpc.selection import select_jobs, select_targets


def test_select_jobs_supports_exact_and_glob_filters_in_config_order():
    jobs = (
        ResolvedGrpcJobConfig(
            name="python.greeter",
            preset="python",
            output=Path("/tmp/python"),
            proto_root=Path("/tmp/protos"),
            protos=("**/*.proto",),
            include_paths=(),
            layout="source_relative",
        ),
        ResolvedGrpcJobConfig(
            name="go.common",
            preset="go",
            output=Path("/tmp/go-common"),
            proto_root=Path("/tmp/protos"),
            protos=("common.proto",),
            include_paths=(),
            layout="source_relative",
        ),
        ResolvedGrpcJobConfig(
            name="go.greeter",
            preset="go",
            output=Path("/tmp/go-greeter"),
            proto_root=Path("/tmp/protos"),
            protos=("greeter.proto",),
            include_paths=(),
            layout="source_relative",
        ),
    )

    selected = select_jobs(jobs, ("go.*", "python.greeter"))

    assert [job.name for job in selected] == [
        "python.greeter",
        "go.common",
        "go.greeter",
    ]


def test_select_jobs_rejects_unmatched_patterns():
    jobs = (
        ResolvedGrpcJobConfig(
            name="python.greeter",
            preset="python",
            output=Path("/tmp/python"),
            proto_root=Path("/tmp/protos"),
            protos=("**/*.proto",),
            include_paths=(),
            layout="source_relative",
        ),
    )

    with pytest.raises(ValueError, match="legacy/raw job"):
        select_jobs(jobs, ("go.*",))


def test_select_targets_supports_exact_and_glob_filters_in_config_order():
    targets = (
        ResolvedGrpcTargetConfig(
            id="python.greeter",
            lang="python",
            out_dir=Path("/tmp/python"),
            source_root=Path("/tmp/protos"),
            files=("**/*.proto",),
            import_roots=(),
        ),
        ResolvedGrpcTargetConfig(
            id="go.common",
            lang="go",
            out_dir=Path("/tmp/go-common"),
            source_root=Path("/tmp/protos"),
            files=("common.proto",),
            import_roots=(),
        ),
        ResolvedGrpcTargetConfig(
            id="go.greeter",
            lang="go",
            out_dir=Path("/tmp/go-greeter"),
            source_root=Path("/tmp/protos"),
            files=("greeter.proto",),
            import_roots=(),
        ),
    )

    selected = select_targets(targets, ("go.*", "python.greeter"))

    assert [target.id for target in selected] == [
        "python.greeter",
        "go.common",
        "go.greeter",
    ]


def test_expand_job_resolves_patterns_and_merges_include_paths(tmp_path):
    proto_root = tmp_path / "protos"
    proto_root.mkdir()
    (proto_root / "common.proto").write_text('syntax = "proto3";\n', encoding="utf-8")
    nested = proto_root / "nested"
    nested.mkdir()
    (nested / "greeter.proto").write_text('syntax = "proto3";\n', encoding="utf-8")
    (nested / "greeter_service.proto").write_text('syntax = "proto3";\n', encoding="utf-8")

    global_include = (tmp_path / "includes").resolve()
    global_include.mkdir()
    job_include = (tmp_path / "job-includes").resolve()
    job_include.mkdir()

    job = ResolvedGrpcJobConfig(
        name="go.greeter",
        preset="go",
        output=(tmp_path / "out").resolve(),
        proto_root=proto_root.resolve(),
        protos=("*.proto", "nested/*.proto", "*.proto"),
        include_paths=(global_include, job_include),
        layout="source_relative",
    )

    planned = expand_job(job, global_include_paths=(global_include,))

    assert planned.import_roots == (global_include, job_include)
    assert planned.source_root == proto_root.resolve()
    assert planned.proto_files == (
        Path("common.proto"),
        Path("nested/greeter.proto"),
        Path("nested/greeter_service.proto"),
    )
    assert planned.layout == "source_relative"
    assert planned.module is None
    assert planned.selection_kind == "job"


def test_expand_target_resolves_patterns_and_merges_import_roots(tmp_path):
    proto_root = tmp_path / "protos"
    proto_root.mkdir()
    (proto_root / "common.proto").write_text('syntax = "proto3";\n', encoding="utf-8")
    nested = proto_root / "nested"
    nested.mkdir()
    (nested / "greeter.proto").write_text('syntax = "proto3";\n', encoding="utf-8")

    global_import = (tmp_path / "includes").resolve()
    global_import.mkdir()
    target_import = (tmp_path / "target-includes").resolve()
    target_import.mkdir()

    target = ResolvedGrpcTargetConfig(
        id="python.greeter",
        lang="python",
        out_dir=(tmp_path / "out").resolve(),
        source_root=proto_root.resolve(),
        files=("*.proto", "nested/*.proto"),
        import_roots=(target_import,),
    )

    planned = expand_target(target, global_import_roots=(global_import,))

    assert planned.import_roots == (global_import, target_import)
    assert planned.source_root == proto_root.resolve()
    assert planned.out_dir == (tmp_path / "out").resolve()
    assert planned.proto_files == (
        Path("common.proto"),
        Path("nested/greeter.proto"),
    )
    assert planned.selection_kind == "target"


def test_expand_target_keeps_python_package_root_metadata(tmp_path):
    proto_root = tmp_path / "protos"
    proto_root.mkdir()
    (proto_root / "greeter.proto").write_text('syntax = "proto3";\n', encoding="utf-8")

    target = ResolvedGrpcTargetConfig(
        id="python.greeter",
        lang="python",
        out_dir=(tmp_path / "out").resolve(),
        source_root=proto_root.resolve(),
        files=("greeter.proto",),
        import_roots=(),
        python_package_root="example.company_pb",
        python_package_root_path=Path("example/company_pb"),
    )

    planned = expand_target(target)

    assert planned.python_package_root == "example.company_pb"
    assert planned.python_package_root_path == Path("example/company_pb")
    assert planned.python_output_path(Path("greeter.proto")) == (
        (tmp_path / "out").resolve() / "example" / "company_pb" / "greeter_pb2.py"
    )


def test_expand_target_go_discovers_module_and_expected_prefix(tmp_path):
    source_root = tmp_path / "protos"
    source_root.mkdir()
    (tmp_path / "go.mod").write_text("module examplegrpc\n\ngo 1.24.0\n", encoding="utf-8")
    (source_root / "commonpb").mkdir()
    (source_root / "commonpb" / "common.proto").write_text(
        """
syntax = "proto3";
option go_package = "examplegrpc/pb/commonpb;commonpb";
""".strip()
        + "\n",
        encoding="utf-8",
    )

    target = ResolvedGrpcTargetConfig(
        id="go.common",
        lang="go",
        out_dir=(tmp_path / "pb").resolve(),
        source_root=source_root.resolve(),
        files=("commonpb/common.proto",),
        import_roots=(),
    )

    planned = expand_target(target)

    assert planned.layout == "go_package"
    assert planned.out_dir == (tmp_path / "pb").resolve()
    assert planned.effective_plugin_out == tmp_path.resolve()
    assert planned.module == "examplegrpc"
    assert planned.module_root == tmp_path.resolve()
    assert planned.expected_go_package_prefix == "examplegrpc/pb"


def test_expand_target_go_rejects_missing_go_package(tmp_path):
    source_root = tmp_path / "protos"
    source_root.mkdir()
    (tmp_path / "go.mod").write_text("module examplegrpc\n", encoding="utf-8")
    (source_root / "greeter.proto").write_text('syntax = "proto3";\n', encoding="utf-8")

    target = ResolvedGrpcTargetConfig(
        id="go.greeter",
        lang="go",
        out_dir=(tmp_path / "pb").resolve(),
        source_root=source_root.resolve(),
        files=("greeter.proto",),
        import_roots=(),
    )

    with pytest.raises(ValueError, match="缺少 option go_package"):
        expand_target(target)


def test_expand_target_go_rejects_go_package_prefix_mismatch(tmp_path):
    source_root = tmp_path / "protos"
    source_root.mkdir()
    (tmp_path / "go.mod").write_text("module examplegrpc\n", encoding="utf-8")
    (source_root / "greeter.proto").write_text(
        """
syntax = "proto3";
option go_package = "examplegrpc/otherpb;greeterpb";
""".strip()
        + "\n",
        encoding="utf-8",
    )

    target = ResolvedGrpcTargetConfig(
        id="go.greeter",
        lang="go",
        out_dir=(tmp_path / "pb").resolve(),
        source_root=source_root.resolve(),
        files=("greeter.proto",),
        import_roots=(),
    )

    with pytest.raises(ValueError, match="go_package 与 out_dir 不一致"):
        expand_target(target)


def test_expand_target_go_rejects_out_dir_outside_go_module(tmp_path):
    source_root = tmp_path / "protos"
    source_root.mkdir()
    (source_root / "greeter.proto").write_text(
        """
syntax = "proto3";
option go_package = "examplegrpc/pb;greeterpb";
""".strip()
        + "\n",
        encoding="utf-8",
    )

    target = ResolvedGrpcTargetConfig(
        id="go.greeter",
        lang="go",
        out_dir=(tmp_path / "pb").resolve(),
        source_root=source_root.resolve(),
        files=("greeter.proto",),
        import_roots=(),
    )

    with pytest.raises(ValueError, match="go.mod"):
        expand_target(target)


def test_expand_target_fails_when_pattern_matches_no_proto_files(tmp_path):
    proto_root = tmp_path / "protos"
    proto_root.mkdir()

    target = ResolvedGrpcTargetConfig(
        id="python.greeter",
        lang="python",
        out_dir=(tmp_path / "out").resolve(),
        source_root=proto_root.resolve(),
        files=("missing.proto",),
        import_roots=(),
    )

    with pytest.raises(ValueError, match="files 未匹配到 proto"):
        expand_target(target)
