from api_blueprint.writer.core.registry import GeneratorTargetSpec, register_target

from .naming import (
    to_swift_identifier,
    to_swift_module_name,
    to_swift_path,
    to_swift_type_name,
)
from .protos import SwiftProtoRegistry
from .selection import SwiftRouteSelection
from .writer import SwiftWriter

register_target(
    GeneratorTargetSpec(
        name="swift-client",
        implemented=True,
        writer_factory=SwiftWriter,
        description="Generate iOS Swift Package API client SDKs.",
    )
)

__all__ = (
    "SwiftProtoRegistry",
    "SwiftRouteSelection",
    "SwiftWriter",
    "to_swift_identifier",
    "to_swift_module_name",
    "to_swift_path",
    "to_swift_type_name",
)
