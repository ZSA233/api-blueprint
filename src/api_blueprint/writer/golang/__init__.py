from api_blueprint.writer.core.registry import GeneratorTargetSpec, register_target

from .blueprint import GolangBlueprint, GolangError, GolangErrorGroup, GolangRouter, GolangRouterGroup
from .common import GolangTagBuilder, GolangType, GolangTypeResolver, PackageName
from .protos import (
    GolangEnum,
    GolangEnumMember,
    GolangFieldWrappedModel,
    GolangPackageLayout,
    GolangProto,
    GolangProtoAlias,
    GolangProtoField,
    GolangProtoFieldView,
    GolangProtoGeneric,
    GolangProtoStruct,
    GolangResponseWrapper,
    ensure_model,
)
from .toolchain import GolangToolchain
from .writer import GolangWriter

register_target(
    GeneratorTargetSpec(
        name="golang",
        implemented=True,
        writer_factory=GolangWriter,
        description="Generate Go contracts and runtime scaffolding.",
    )
)

__all__ = (
    "GolangBlueprint",
    "GolangEnum",
    "GolangEnumMember",
    "GolangError",
    "GolangErrorGroup",
    "GolangFieldWrappedModel",
    "GolangPackageLayout",
    "GolangProto",
    "GolangProtoAlias",
    "GolangProtoField",
    "GolangProtoFieldView",
    "GolangProtoGeneric",
    "GolangProtoStruct",
    "GolangResponseWrapper",
    "GolangRouter",
    "GolangRouterGroup",
    "GolangTagBuilder",
    "GolangToolchain",
    "GolangType",
    "GolangTypeResolver",
    "GolangWriter",
    "PackageName",
    "ensure_model",
)
