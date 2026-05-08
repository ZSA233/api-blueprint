from api_blueprint.writer.core.registry import GeneratorTargetSpec, register_target

from .blueprint import KotlinApiGroup, KotlinBlueprint, KotlinRoute
from .naming import to_kotlin_property_name, to_kotlin_type_name, to_package_path
from .planner import (
    KotlinBlueprintPlan,
    KotlinHttpTransportPlan,
    KotlinRouteGroupPlan,
    KotlinRuntimePlan,
    build_kotlin_blueprint_plan,
)
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
    "KotlinBlueprintPlan",
    "KotlinHttpTransportPlan",
    "KotlinProto",
    "KotlinProtoField",
    "KotlinProtoRegistry",
    "KotlinRouteGroupPlan",
    "KotlinResolvedType",
    "KotlinRoute",
    "KotlinRouteSelection",
    "KotlinRuntimePlan",
    "KotlinTypeResolver",
    "KotlinWriter",
    "build_kotlin_blueprint_plan",
    "matches_rule",
    "to_kotlin_property_name",
    "to_kotlin_type_name",
    "to_package_path",
)
