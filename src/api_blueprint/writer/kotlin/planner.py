from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .protos import KotlinProto

if TYPE_CHECKING:
    from .blueprint import KotlinApiGroup, KotlinBlueprint
    from .writer import KotlinWriter


@dataclass(frozen=True)
class KotlinRuntimePlan:
    directory: Path
    generated_files: tuple[tuple[str, str], ...]
    user_files: tuple[tuple[str, str], ...]
    models_file: Path
    shared_protos: tuple[KotlinProto, ...]


@dataclass(frozen=True)
class KotlinHttpTransportPlan:
    directory: Path
    generated_files: tuple[tuple[str, str], ...]
    user_files: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class KotlinRouteGroupPlan:
    group: "KotlinApiGroup"
    directory: Path
    models_file: Path
    client_file: Path
    facade_file: Path
    protos: tuple[KotlinProto, ...]


@dataclass(frozen=True)
class KotlinBlueprintPlan:
    root_directory: Path
    runtime: KotlinRuntimePlan
    http_transport: KotlinHttpTransportPlan
    route_groups: tuple[KotlinRouteGroupPlan, ...]


def build_kotlin_blueprint_plan(writer: "KotlinWriter", bp: "KotlinBlueprint") -> KotlinBlueprintPlan:
    root_directory = writer.root_dir(bp)
    runtime_dir = root_directory / "runtime"
    routes_dir = root_directory / "routes"
    http_dir = root_directory / "transports" / "http"
    route_groups = tuple(
        KotlinRouteGroupPlan(
            group=group,
            directory=routes_dir / group.package_path,
            models_file=routes_dir / group.package_path / f"Gen{group.class_name}Models.kt",
            client_file=routes_dir / group.package_path / f"Gen{group.class_name}.kt",
            facade_file=routes_dir / group.package_path / f"{group.class_name}.kt",
            protos=tuple(bp.registry.filter(module=group.slug)),
        )
        for group in bp.groups.values()
    )
    return KotlinBlueprintPlan(
        root_directory=root_directory,
        runtime=KotlinRuntimePlan(
            directory=runtime_dir,
            generated_files=(
                ("GenApiException.kt", "ApiException.kt"),
                ("GenApiErrors.kt", "ApiErrors.kt"),
                ("GenApiErrorCatalog.kt", "ApiErrorCatalog.kt"),
                ("GenApiTransport.kt", "ApiTransport.kt"),
                ("GenApiClient.kt", "GenApiClient.kt"),
            ),
            user_files=(("ApiClient.kt", "ApiClient.kt"),),
            models_file=runtime_dir / "GenModels.kt",
            shared_protos=tuple(bp.registry.filter(module="shared")),
        ),
        http_transport=KotlinHttpTransportPlan(
            directory=http_dir,
            generated_files=(
                ("GenHttpApiConfig.kt", "HttpApiConfig.kt"),
                ("GenOkHttpApiTransport.kt", "OkHttpApiTransport.kt"),
            ),
            user_files=(("HttpApiClient.kt", "HttpApiClient.kt"),),
        ),
        route_groups=route_groups,
    )
