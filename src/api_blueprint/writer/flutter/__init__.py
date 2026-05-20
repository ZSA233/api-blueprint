from api_blueprint.writer.core.registry import GeneratorTargetSpec, register_target

from .blueprint import FlutterApiGroup, FlutterBlueprint, FlutterRoute
from .naming import to_dart_file_stem, to_dart_identifier, to_dart_path, to_dart_type_name
from .planner import (
    FlutterBlueprintPlan,
    FlutterHttpTransportPlan,
    FlutterRouteGroupPlan,
    FlutterRuntimePlan,
    build_flutter_blueprint_plan,
)
from .protos import DartProto, DartProtoField, DartProtoRegistry, DartResolvedType, DartTypeResolver
from .selection import FlutterRouteSelection
from .writer import FlutterWriter

register_target(
    GeneratorTargetSpec(
        name="flutter-client",
        implemented=True,
        writer_factory=FlutterWriter,
        description="Generate pure Dart API client packages for Flutter applications.",
    )
)

__all__ = (
    "DartProto",
    "DartProtoField",
    "DartProtoRegistry",
    "DartResolvedType",
    "DartTypeResolver",
    "FlutterApiGroup",
    "FlutterBlueprint",
    "FlutterBlueprintPlan",
    "FlutterHttpTransportPlan",
    "FlutterRoute",
    "FlutterRouteGroupPlan",
    "FlutterRouteSelection",
    "FlutterRuntimePlan",
    "FlutterWriter",
    "build_flutter_blueprint_plan",
    "to_dart_file_stem",
    "to_dart_identifier",
    "to_dart_path",
    "to_dart_type_name",
)
