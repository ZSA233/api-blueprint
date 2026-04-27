from api_blueprint.writer.core.registry import GeneratorTargetSpec, register_target

from .blueprint import KotlinApiGroup, KotlinBlueprint, KotlinRoute
from .naming import to_kotlin_property_name, to_kotlin_type_name, to_package_path
from .protos import KotlinProto, KotlinProtoField, KotlinProtoRegistry, KotlinResolvedType, KotlinTypeResolver
from .selection import KotlinRouteSelection, matches_rule
from .writer import KotlinWriter

register_target(
    GeneratorTargetSpec(
        name="kotlin",
        implemented=True,
        writer_factory=KotlinWriter,
        description="Generate Kotlin Android API clients and contracts.",
    )
)

__all__ = (
    "KotlinApiGroup",
    "KotlinBlueprint",
    "KotlinProto",
    "KotlinProtoField",
    "KotlinProtoRegistry",
    "KotlinResolvedType",
    "KotlinRoute",
    "KotlinRouteSelection",
    "KotlinTypeResolver",
    "KotlinWriter",
    "matches_rule",
    "to_kotlin_property_name",
    "to_kotlin_type_name",
    "to_package_path",
)

