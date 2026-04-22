from __future__ import annotations

from pathlib import Path

from api_blueprint.config import ResolvedGrpcConfig, ResolvedGrpcJobConfig
from api_blueprint.writer.grpc import GrpcWriter


def test_plan_jobs_uses_job_proto_root_override_instead_of_global_root(tmp_path):
    global_proto_root = tmp_path / "protos"
    service_proto_root = global_proto_root / "services" / "exampledomain" / "api"
    feature_dir = service_proto_root / "feature" / "v1"
    feature_dir.mkdir(parents=True)
    (feature_dir / "example.proto").write_text('syntax = "proto3";\n', encoding="utf-8")

    config = ResolvedGrpcConfig(
        proto_root=global_proto_root.resolve(),
        include_paths=(),
        jobs=(
            ResolvedGrpcJobConfig(
                name="python.services",
                preset="python",
                output=(tmp_path / "out").resolve(),
                proto_root=service_proto_root.resolve(),
                protos=("feature/v1/example.proto",),
                include_paths=(),
                layout="source_relative",
            ),
        ),
    )

    planned = GrpcWriter(config).plan_jobs()

    assert len(planned) == 1
    assert planned[0].proto_root == service_proto_root.resolve()
    assert planned[0].proto_files == (Path("feature/v1/example.proto"),)
