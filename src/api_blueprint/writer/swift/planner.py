from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .protos import SwiftProto

if TYPE_CHECKING:
    from .blueprint import SwiftApiGroup, SwiftBlueprint
    from .writer import SwiftWriter


@dataclass(frozen=True)
class SwiftRuntimePlan:
    directory: Path
    generated_files: tuple[tuple[str, str], ...]
    user_files: tuple[tuple[str, str], ...]
    types_file: Path
    shared_protos: tuple[SwiftProto, ...]
    binary_runtime_file: Path


@dataclass(frozen=True)
class SwiftHttpTransportPlan:
    directory: Path
    generated_files: tuple[tuple[str, str], ...]
    user_files: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class SwiftRouteGroupPlan:
    group: "SwiftApiGroup"
    directory: Path
    client_file: Path
    facade_file: Path
    types_file: Path
    types_facade_file: Path
    binary_file: Path
    protos: tuple[SwiftProto, ...]


@dataclass(frozen=True)
class SwiftBlueprintPlan:
    root_directory: Path
    root_client_file: Path
    root_facade_file: Path
    runtime: SwiftRuntimePlan
    http_transport: SwiftHttpTransportPlan
    route_groups: tuple[SwiftRouteGroupPlan, ...]


def build_swift_blueprint_plan(writer: "SwiftWriter", bp: "SwiftBlueprint") -> SwiftBlueprintPlan:
    root_directory = writer.source_dir / bp.root_path
    runtime_dir = root_directory / "Runtime"
    routes_dir = root_directory / "Routes"
    http_dir = root_directory / "Transports" / "HTTP"
    route_groups = tuple(
        SwiftRouteGroupPlan(
            group=group,
            directory=routes_dir / group.path,
            client_file=routes_dir / group.path / f"Gen{group.type_stem}API.swift",
            facade_file=routes_dir / group.path / f"{group.type_stem}API.swift",
            types_file=routes_dir / group.path / f"Gen{group.type_stem}Types.swift",
            types_facade_file=routes_dir / group.path / f"{group.type_stem}Types.swift",
            binary_file=routes_dir / group.path / "GenBinary.swift",
            protos=tuple(bp.registry.filter(module=group.slug)),
        )
        for group in bp.groups.values()
    )
    return SwiftBlueprintPlan(
        root_directory=root_directory,
        root_client_file=root_directory / f"Gen{bp.root_client}.swift",
        root_facade_file=root_directory / f"{bp.root_client}.swift",
        runtime=SwiftRuntimePlan(
            directory=runtime_dir,
            generated_files=(
                ("GenAPITransport.swift", "GenAPITransport.swift"),
                ("GenAPIClient.swift", "GenAPIClient.swift"),
                ("GenAPIErrors.swift", "GenAPIErrors.swift"),
                ("GenAPIErrorLookup.swift", "GenAPIErrorLookup.swift"),
            ),
            user_files=(("APICoding.swift", "APICoding.swift"),),
            types_file=runtime_dir / "GenAPITypes.swift",
            shared_protos=tuple(bp.registry.filter(module="shared")),
            binary_runtime_file=runtime_dir / "Binary" / "GenBinaryRuntime.swift",
        ),
        http_transport=SwiftHttpTransportPlan(
            directory=http_dir,
            generated_files=(
                ("GenHTTPAPIConfig.swift", "GenHTTPAPIConfig.swift"),
                ("GenURLSessionAPITransport.swift", "GenURLSessionAPITransport.swift"),
                ("GenHTTPConnection.swift", "GenHTTPConnection.swift"),
            ),
            user_files=(("HTTPAPIClient.swift", "HTTPAPIClient.swift"),),
        ),
        route_groups=route_groups,
    )
