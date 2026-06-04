from api_blueprint.writer.core.registry import GeneratorTargetSpec, register_target

from .blueprint import JavaApiGroup, JavaBlueprint, JavaRoute
from .client import JavaClientWriter
from .naming import to_java_member_name, to_java_package_path, to_java_type_name, to_package_path
from .planner import (
    JavaBlueprintPlan,
    JavaHttpTransportPlan,
    JavaRouteGroupPlan,
    JavaRuntimePlan,
    build_java_blueprint_plan,
)
from .protos import JavaEnum, JavaModelCatalog, JavaSchema, JavaSchemaField
from .server import JavaServerWriter
from .writer import JavaBaseWriter

register_target(
    GeneratorTargetSpec(
        name="java-client",
        implemented=True,
        writer_factory=JavaClientWriter,
        description="Generate Java 17 API clients with an injected transport and JDK HTTP adapter.",
    )
)
register_target(
    GeneratorTargetSpec(
        name="java-server",
        implemented=True,
        writer_factory=JavaServerWriter,
        description="Generate Java Spring MVC contract-boundary annotations, types, adapters, and runtime assertions.",
    )
)

__all__ = (
    "JavaApiGroup",
    "JavaBaseWriter",
    "JavaBlueprint",
    "JavaBlueprintPlan",
    "JavaClientWriter",
    "JavaEnum",
    "JavaHttpTransportPlan",
    "JavaModelCatalog",
    "JavaRoute",
    "JavaRouteGroupPlan",
    "JavaRuntimePlan",
    "JavaSchema",
    "JavaSchemaField",
    "JavaServerWriter",
    "build_java_blueprint_plan",
    "to_java_member_name",
    "to_java_package_path",
    "to_java_type_name",
    "to_package_path",
)
