from api_blueprint.writer.core.registry import GeneratorTargetSpec, register_target

from .blueprint import TypeScriptBlueprint, TypeScriptRoute, TypeScriptRouterGroup, TypeScriptViewGroup
from .naming import cap_token, to_camel, to_ts_identifier, to_ts_name
from .protos import (
    TypeScriptProto,
    TypeScriptProtoField,
    TypeScriptProtoRegistry,
    TypeScriptResolvedType,
    TypeScriptTypeResolver,
)
from .writer import TypeScriptWriter

register_target(
    GeneratorTargetSpec(
        name="typescript",
        implemented=True,
        writer_factory=TypeScriptWriter,
        description="Generate TypeScript client and contract snapshots.",
    )
)

__all__ = (
    "TypeScriptBlueprint",
    "TypeScriptProto",
    "TypeScriptProtoField",
    "TypeScriptProtoRegistry",
    "TypeScriptResolvedType",
    "TypeScriptRoute",
    "TypeScriptRouterGroup",
    "TypeScriptTypeResolver",
    "TypeScriptViewGroup",
    "TypeScriptWriter",
    "cap_token",
    "to_camel",
    "to_ts_identifier",
    "to_ts_name",
)
