from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .protos import DartProto

if TYPE_CHECKING:
    from .blueprint import FlutterApiGroup, FlutterBlueprint
    from .writer import FlutterWriter


@dataclass(frozen=True)
class FlutterRuntimePlan:
    directory: Path
    generated_files: tuple[tuple[str, str], ...]
    user_files: tuple[tuple[str, str], ...]
    types_file: Path
    shared_protos: tuple[DartProto, ...]
    binary_runtime_file: Path


@dataclass(frozen=True)
class FlutterHttpTransportPlan:
    directory: Path
    generated_files: tuple[tuple[str, str], ...]
    user_files: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class FlutterRouteGroupPlan:
    group: "FlutterApiGroup"
    directory: Path
    client_file: Path
    facade_file: Path
    types_file: Path
    types_facade_file: Path
    binary_file: Path
    binary_facade_file: Path
    protos: tuple[DartProto, ...]


@dataclass(frozen=True)
class FlutterBlueprintPlan:
    root_directory: Path
    root_barrel_file: Path
    root_facade_file: Path
    runtime: FlutterRuntimePlan
    http_transport: FlutterHttpTransportPlan
    route_groups: tuple[FlutterRouteGroupPlan, ...]


def build_flutter_blueprint_plan(writer: "FlutterWriter", bp: "FlutterBlueprint") -> FlutterBlueprintPlan:
    root_directory = writer.source_dir / bp.root_path
    runtime_dir = root_directory / "runtime"
    routes_dir = root_directory / "routes"
    http_dir = root_directory / "transports" / "http"
    route_groups = tuple(
        FlutterRouteGroupPlan(
            group=group,
            directory=routes_dir / group.path,
            client_file=routes_dir / group.path / f"gen_{group.file_stem}_api.dart",
            facade_file=routes_dir / group.path / f"{group.file_stem}_api.dart",
            types_file=routes_dir / group.path / f"gen_{group.file_stem}_types.dart",
            types_facade_file=routes_dir / group.path / f"{group.file_stem}_types.dart",
            binary_file=routes_dir / group.path / "gen_binary.dart",
            binary_facade_file=routes_dir / group.path / "binary.dart",
            protos=tuple(bp.registry.filter(module=group.slug)),
        )
        for group in bp.groups.values()
    )
    return FlutterBlueprintPlan(
        root_directory=root_directory,
        root_barrel_file=root_directory / f"gen_{bp.root_path.rsplit('/', 1)[-1]}.dart",
        root_facade_file=root_directory / f"{bp.root_path.rsplit('/', 1)[-1]}.dart",
        runtime=FlutterRuntimePlan(
            directory=runtime_dir,
            generated_files=(
                ("gen_api_transport.dart", "gen_api_transport.dart"),
                ("gen_api_client.dart", "gen_api_client.dart"),
                ("gen_api_errors.dart", "gen_api_errors.dart"),
                ("gen_api_error_lookup.dart", "gen_api_error_lookup.dart"),
            ),
            user_files=(
                ("api_client.dart", "api_client.dart"),
                ("api_json_codecs.dart", "api_json_codecs.dart"),
            ),
            types_file=runtime_dir / "gen_api_types.dart",
            shared_protos=tuple(bp.registry.filter(module="shared")),
            binary_runtime_file=runtime_dir / "binary" / "gen_binary_runtime.dart",
        ),
        http_transport=FlutterHttpTransportPlan(
            directory=http_dir,
            generated_files=(
                ("gen_http_api_config.dart", "gen_http_api_config.dart"),
                ("gen_http_api_transport.dart", "gen_http_api_transport.dart"),
                ("gen_http_connection.dart", "gen_http_connection.dart"),
            ),
            user_files=(("http_api_client.dart", "http_api_client.dart"),),
        ),
        route_groups=route_groups,
    )
