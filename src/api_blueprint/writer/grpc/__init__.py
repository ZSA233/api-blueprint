from api_blueprint.writer.core.registry import GeneratorTargetSpec, register_target

from .proto_writer import render_proto_files

register_target(
    GeneratorTargetSpec(
        name="grpc-proto",
        implemented=True,
        writer_factory=render_proto_files,
        description="Generate gRPC proto files from a ContractGraph.",
    )
)

__all__ = (
    "render_proto_files",
)
