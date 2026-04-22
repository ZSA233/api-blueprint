from __future__ import annotations

from pathlib import Path

import pytest

from api_blueprint.config import ResolvedGrpcJobConfig
from api_blueprint.writer.grpc.selection import expand_job, select_jobs


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

    with pytest.raises(ValueError, match="未匹配到任何job"):
        select_jobs(jobs, ("go.*",))


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

    assert planned.include_paths == (global_include, job_include)
    assert planned.proto_root == proto_root.resolve()
    assert planned.proto_files == (
        Path("common.proto"),
        Path("nested/greeter.proto"),
        Path("nested/greeter_service.proto"),
    )
    assert planned.layout == "source_relative"
    assert planned.module is None


def test_expand_job_preserves_go_package_layout_and_module(tmp_path):
    proto_root = tmp_path / "protos"
    proto_root.mkdir()
    nested = proto_root / "shared" / "example" / "api" / "v1"
    nested.mkdir(parents=True)
    (nested / "example.proto").write_text('syntax = "proto3";\n', encoding="utf-8")

    job = ResolvedGrpcJobConfig(
        name="go.example",
        preset="go",
        output=(tmp_path / "module-root").resolve(),
        proto_root=proto_root.resolve(),
        protos=("shared/example/api/v1/example.proto",),
        include_paths=(),
        layout="go_package",
        module="examplemod",
    )

    planned = expand_job(job)

    assert planned.proto_root == proto_root.resolve()
    assert planned.layout == "go_package"
    assert planned.module == "examplemod"
    assert planned.proto_files == (Path("shared/example/api/v1/example.proto"),)


def test_expand_job_uses_job_proto_root_override_for_python_source_relative_layout(tmp_path):
    global_proto_root = tmp_path / "protos"
    service_proto_root = global_proto_root / "services" / "exampledomain" / "api"
    feature_dir = service_proto_root / "feature" / "v1"
    feature_dir.mkdir(parents=True)
    (feature_dir / "example.proto").write_text('syntax = "proto3";\n', encoding="utf-8")

    global_include = (tmp_path / "includes").resolve()
    global_include.mkdir()
    job_include = (tmp_path / "job-includes").resolve()
    job_include.mkdir()

    job = ResolvedGrpcJobConfig(
        name="python.services",
        preset="python",
        output=(tmp_path / "out").resolve(),
        proto_root=service_proto_root.resolve(),
        protos=("feature/v1/example.proto",),
        include_paths=(job_include,),
        layout="source_relative",
    )

    planned = expand_job(job, global_include_paths=(global_include,))

    assert planned.proto_root == service_proto_root.resolve()
    assert planned.include_paths == (global_include, job_include)
    assert planned.proto_files == (Path("feature/v1/example.proto"),)


def test_expand_job_fails_when_pattern_matches_no_proto_files(tmp_path):
    proto_root = tmp_path / "protos"
    proto_root.mkdir()

    job = ResolvedGrpcJobConfig(
        name="python.greeter",
        preset="python",
        output=(tmp_path / "out").resolve(),
        proto_root=proto_root.resolve(),
        protos=("missing.proto",),
        include_paths=(),
        layout="source_relative",
    )

    with pytest.raises(ValueError, match="proto pattern"):
        expand_job(job)
