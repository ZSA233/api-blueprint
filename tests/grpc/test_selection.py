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
            protos=("**/*.proto",),
            include_paths=(),
        ),
        ResolvedGrpcJobConfig(
            name="go.common",
            preset="go",
            output=Path("/tmp/go-common"),
            protos=("common.proto",),
            include_paths=(),
        ),
        ResolvedGrpcJobConfig(
            name="go.greeter",
            preset="go",
            output=Path("/tmp/go-greeter"),
            protos=("greeter.proto",),
            include_paths=(),
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
            protos=("**/*.proto",),
            include_paths=(),
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
        protos=("*.proto", "nested/*.proto", "*.proto"),
        include_paths=(global_include, job_include),
    )

    planned = expand_job(job, proto_root=proto_root, global_include_paths=(global_include,))

    assert planned.include_paths == (global_include, job_include)
    assert planned.proto_files == (
        Path("common.proto"),
        Path("nested/greeter.proto"),
        Path("nested/greeter_service.proto"),
    )


def test_expand_job_fails_when_pattern_matches_no_proto_files(tmp_path):
    proto_root = tmp_path / "protos"
    proto_root.mkdir()

    job = ResolvedGrpcJobConfig(
        name="python.greeter",
        preset="python",
        output=(tmp_path / "out").resolve(),
        protos=("missing.proto",),
        include_paths=(),
    )

    with pytest.raises(ValueError, match="proto pattern"):
        expand_job(job, proto_root=proto_root)
