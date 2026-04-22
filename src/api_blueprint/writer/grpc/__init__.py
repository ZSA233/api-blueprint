from api_blueprint.writer.core.registry import GeneratorTargetSpec, register_target

from .models import GrpcGenerationJob, GrpcPreset
from .selection import expand_job, select_jobs
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
    "GrpcPreset",
    "GrpcToolchain",
    "GrpcWriter",
    "expand_job",
    "select_jobs",
)
