from api_blueprint.writer.core.registry import GeneratorTargetSpec, register_target

from .common import GolangTagBuilder, GolangType, GolangTypeResolver, PackageName
from .route_view import GoRouteProtocolView, GolangRouter
from .server import GolangBlueprint, GolangError, GolangErrorGroup, GolangRouterGroup, GolangWriter
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
    GolangResponseEnvelope,
    ensure_model,
)
from .toolchain import GolangToolchain
from .client import GolangClientWriter

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
    "GolangClientWriter",
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
    "GolangResponseEnvelope",
    "GolangRouter",
    "GolangRouterGroup",
    "GolangTagBuilder",
    "GolangToolchain",
    "GolangType",
    "GolangTypeResolver",
    "GolangWriter",
    "GoRouteProtocolView",
    "PackageName",
    "ensure_model",
)
