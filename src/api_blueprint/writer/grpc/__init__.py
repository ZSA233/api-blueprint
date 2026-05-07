from api_blueprint.writer.core.registry import GeneratorTargetSpec, register_target

from .proto_writer import render_proto_files
from .toolchain import generate_go_stubs, generate_python_stubs

register_target(
    GeneratorTargetSpec(
        name="grpc-proto",
        implemented=True,
        writer_factory=render_proto_files,
        description="Generate gRPC proto files from a ContractGraph.",
    )
)
register_target(
    GeneratorTargetSpec(
        name="grpc-go",
        implemented=True,
        writer_factory=generate_go_stubs,
        description="Compile generated gRPC proto files into Go protobuf/gRPC stubs.",
    )
)
register_target(
    GeneratorTargetSpec(
        name="grpc-python",
        implemented=True,
        writer_factory=generate_python_stubs,
        description="Compile generated gRPC proto files into Python protobuf/gRPC stubs.",
    )
)

__all__ = (
    "generate_go_stubs",
    "generate_python_stubs",
    "render_proto_files",
)
