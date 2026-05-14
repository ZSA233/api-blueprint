from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .blueprint import JavaApiGroup, JavaBlueprint
    from .writer import JavaBaseWriter


@dataclass(frozen=True)
class JavaRuntimePlan:
    directory: Path
    binary_directory: Path


@dataclass(frozen=True)
class JavaHttpTransportPlan:
    directory: Path


@dataclass(frozen=True)
class JavaRouteGroupPlan:
    group: "JavaApiGroup"
    directory: Path
    binary_file: Path
    legacy_binary_directory: Path


@dataclass(frozen=True)
class JavaBlueprintPlan:
    root_directory: Path
    runtime: JavaRuntimePlan
    http_transport: JavaHttpTransportPlan
    route_groups: tuple[JavaRouteGroupPlan, ...]


def build_java_blueprint_plan(writer: "JavaBaseWriter", bp: "JavaBlueprint") -> JavaBlueprintPlan:
    root_directory = writer.root_dir(bp)
    runtime_dir = root_directory / "runtime"
    http_dir = root_directory / "transports" / "http"
    routes_dir = root_directory / "routes"
    return JavaBlueprintPlan(
        root_directory=root_directory,
        runtime=JavaRuntimePlan(
            directory=runtime_dir,
            binary_directory=runtime_dir / "binary",
        ),
        http_transport=JavaHttpTransportPlan(directory=http_dir),
        route_groups=tuple(
            JavaRouteGroupPlan(
                group=group,
                directory=routes_dir / group.package_path,
                binary_file=routes_dir / group.package_path / "GenBinary.java",
                legacy_binary_directory=routes_dir / group.package_path / "binary",
            )
            for group in bp.groups.values()
        ),
    )
