from api_blueprint.writer.core.registry import GeneratorTargetSpec, register_target

from .blueprint import PythonBlueprint, PythonRequestParam, PythonRoute, PythonRouteGroup
from .naming import to_package_segments, to_path_segments, to_py_class_name, to_py_identifier
from .planner import (
    PythonBlueprintPlan,
    PythonHttpTransportPlan,
    PythonRouteGroupPlan,
    PythonRuntimePlan,
    build_python_blueprint_plan,
)
from .writer import PythonClientWriter, PythonServerWriter

register_target(
    GeneratorTargetSpec(
        name="python-client",
        implemented=True,
        writer_factory=PythonClientWriter,
        description="Generate async Python API clients and HTTP transport scaffolding.",
    )
)
register_target(
    GeneratorTargetSpec(
        name="python-server",
        implemented=True,
        writer_factory=PythonServerWriter,
        description="Generate Python service contracts and FastAPI transport scaffolding.",
    )
)

__all__ = (
    "PythonBlueprint",
    "PythonBlueprintPlan",
    "PythonClientWriter",
    "PythonHttpTransportPlan",
    "PythonRequestParam",
    "PythonRoute",
    "PythonRouteGroup",
    "PythonRouteGroupPlan",
    "PythonRuntimePlan",
    "PythonServerWriter",
    "build_python_blueprint_plan",
    "to_package_segments",
    "to_path_segments",
    "to_py_class_name",
    "to_py_identifier",
)
