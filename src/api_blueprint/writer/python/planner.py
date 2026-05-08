from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .blueprint import PythonBlueprint, PythonRouteGroup
    from .writer import PythonBaseWriter


@dataclass(frozen=True)
class PythonRuntimePlan:
    directory: Path
    generated_file: Path
    public_file: Path


@dataclass(frozen=True)
class PythonHttpTransportPlan:
    directory: Path
    generated_file: Path
    public_file: Path


@dataclass(frozen=True)
class PythonRouteGroupPlan:
    group: "PythonRouteGroup"
    directory: Path
    generated_file: Path
    public_file: Path
    legacy_public_file: Path


@dataclass(frozen=True)
class PythonBlueprintPlan:
    root_directory: Path
    routes_directory: Path
    transports_directory: Path
    runtime: PythonRuntimePlan
    http_transport: PythonHttpTransportPlan
    route_groups: tuple[PythonRouteGroupPlan, ...]


def build_python_blueprint_plan(writer: "PythonBaseWriter", bp: "PythonBlueprint") -> PythonBlueprintPlan:
    root_directory = writer.root_dir(bp)
    runtime_dir = root_directory / "runtime"
    routes_dir = root_directory / "routes"
    transports_dir = root_directory / "transports"
    http_dir = transports_dir / "http"
    route_groups = tuple(
        PythonRouteGroupPlan(
            group=group,
            directory=_group_dir(routes_dir, group),
            generated_file=_group_dir(routes_dir, group) / writer.route_template,
            public_file=_group_dir(routes_dir, group) / writer.route_template.replace("gen_", ""),
            legacy_public_file=_legacy_group_dir(routes_dir, group) / writer.route_template.replace("gen_", ""),
        )
        for group in bp.groups.values()
    )
    return PythonBlueprintPlan(
        root_directory=root_directory,
        routes_directory=routes_dir,
        transports_directory=transports_dir,
        runtime=PythonRuntimePlan(
            directory=runtime_dir,
            generated_file=runtime_dir / writer.runtime_template,
            public_file=runtime_dir / writer.runtime_template.replace("gen_", ""),
        ),
        http_transport=PythonHttpTransportPlan(
            directory=http_dir,
            generated_file=http_dir / writer.transport_template,
            public_file=http_dir / writer.transport_template.replace("gen_", ""),
        ),
        route_groups=route_groups,
    )


def _group_dir(routes_dir: Path, group: "PythonRouteGroup") -> Path:
    group_dir = routes_dir
    for segment in group.segments:
        group_dir /= segment
    return group_dir


def _legacy_group_dir(routes_dir: Path, group: "PythonRouteGroup") -> Path:
    group_dir = routes_dir
    for segment in group.legacy_segments:
        group_dir /= segment
    return group_dir
