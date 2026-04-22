from api_blueprint.writer.core.registry import GeneratorTargetSpec, register_target

from .models import GrpcGenerationJob, GrpcLayout, GrpcPreset
from .planner import expand_job, expand_target
from .selection import select_jobs, select_targets
from .toolchain import GrpcToolchain
from .writer import GrpcWriter

register_target(
    GeneratorTargetSpec(
        name="grpc",
        implemented=True,
        writer_factory=GrpcWriter,
        description="Generate gRPC outputs from existing proto trees.",
    )
)

__all__ = (
    "GrpcGenerationJob",
    "GrpcLayout",
    "GrpcPreset",
    "GrpcToolchain",
    "GrpcWriter",
    "expand_job",
    "expand_target",
    "select_jobs",
    "select_targets",
)
