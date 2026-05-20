from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from api_blueprint.config.loader import normalize_config_path
from api_blueprint.config.models import (
    Config,
    TargetKind,
    WailsFrontendMode,
    WailsVersion,
    default_wails_overlay_name,
)
from api_blueprint.route_selection import normalize_selection_rules


@dataclass(frozen=True)
class ResolvedTargetConfig:
    output: Path | None
    upstream: str | None = None
    module: str | None = None
    base_url: str | None = None
    base_url_expr: str | None = None


@dataclass(frozen=True)
class ResolvedApiTargetConfig:
    id: str
    kind: TargetKind
    out_dir: Path | None = None
    module: str | None = None
    base_url: str | None = None
    base_url_expr: str | None = None
    package: str | None = None
    formats: tuple[str, ...] = ()
    version: WailsVersion | None = None
    frontend_mode: WailsFrontendMode = "external"
    overlay_name: str | None = None
    server: str | None = None
    clients: tuple[str, ...] = ()
    proto: str | None = None
    source_root: Path | None = None
    files: tuple[str, ...] = ()
    import_roots: tuple[Path, ...] = ()
    go_package_prefix: str | None = None
    python_package_root: str | None = None
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    proto_files: tuple["ResolvedGrpcProtoFileConfig", ...] = ()


@dataclass(frozen=True)
class ResolvedGrpcProtoFileConfig:
    file: str
    package: str | None = None
    go_package: str | None = None
    schema_modules: tuple[str, ...] = ()
    schema_names: tuple[str, ...] = ()
    route_paths: tuple[str, ...] = ()
    route_ids: tuple[str, ...] = ()
    service_ids: tuple[str, ...] = ()
    service: str | None = None


@dataclass(frozen=True)
class ResolvedWailsTargetConfig:
    id: str
    version: WailsVersion
    overlay_name: str
    frontend_mode: WailsFrontendMode
    include: tuple[str, ...]
    exclude: tuple[str, ...]


@dataclass(frozen=True)
class ResolvedWailsConfig:
    targets: tuple[ResolvedWailsTargetConfig, ...]


@dataclass(frozen=True)
class ResolvedConfig:
    path: Path
    project_root: Path
    entrypoint_root: Path
    raw: Config
    targets: tuple[ResolvedApiTargetConfig, ...]


def resolve_output_path(config_path: Path, output: str | None) -> Path | None:
    if output is None:
        return None

    target = Path(output)
    if not target.is_absolute():
        target = (config_path.parent / target).resolve()
    return target


def resolve_path_list(config_path: Path, entries: list[str] | tuple[str, ...]) -> tuple[Path, ...]:
    resolved: list[Path] = []
    for entry in entries:
        target = Path(entry)
        if not target.is_absolute():
            target = (config_path.parent / target).resolve()
        resolved.append(target)
    return tuple(resolved)


def resolve_unique_path_list(config_path: Path, entries: list[str] | tuple[str, ...]) -> tuple[Path, ...]:
    resolved: list[Path] = []
    seen: set[str] = set()
    for path in resolve_path_list(config_path, entries):
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        resolved.append(path)
    return tuple(resolved)


def resolve_config(path: str | Path | None) -> ResolvedConfig:
    normalized = normalize_config_path(path)
    raw = Config.load(normalized)
    return ResolvedConfig(
        path=normalized,
        project_root=normalized.parent,
        entrypoint_root=normalized.parent,
        raw=raw,
        targets=resolve_api_targets(normalized, raw),
    )


def resolve_api_targets(config_path: Path, raw: Config) -> tuple[ResolvedApiTargetConfig, ...]:
    target_map = {target.id: target for target in raw.targets}
    resolved: list[ResolvedApiTargetConfig] = []
    for target in raw.targets:
        if target.kind in {"http-transport", "wails-transport"}:
            if target.server is None:
                raise ValueError(f"target[{target.id}] {target.kind} requires server")
            server = target_map.get(target.server)
            if server is None:
                raise ValueError(f"target[{target.id}] references unknown server target: {target.server}")
            if target.kind == "wails-transport" and server.kind != "go-server":
                raise ValueError(f"target[{target.id}] wails-transport server must reference a go-server target")
            if target.kind == "http-transport" and server.kind not in {
                "go-server",
                "python-server",
                "java-server",
                "kotlin-server",
            }:
                raise ValueError(f"target[{target.id}] http-transport server must reference a server target")

            for client_id in target.clients:
                client = target_map.get(client_id)
                if client is None:
                    raise ValueError(f"target[{target.id}] references unknown client target: {client_id}")
                if target.kind == "wails-transport" and client.kind != "typescript-client":
                    raise ValueError(
                        f"target[{target.id}] wails-transport clients must reference typescript-client targets"
                    )
                if target.kind == "http-transport" and client.kind not in {
                    "go-client",
                    "typescript-client",
                    "kotlin-client",
                    "python-client",
                    "java-client",
                    "flutter-client",
                }:
                    raise ValueError(f"target[{target.id}] http-transport clients must reference client targets")

        if target.kind in {"grpc-go", "grpc-python"}:
            if target.proto is not None:
                proto = target_map.get(target.proto)
                if proto is None:
                    raise ValueError(f"target[{target.id}] references unknown proto target: {target.proto}")
                if proto.kind != "grpc-proto":
                    raise ValueError(f"target[{target.id}] {target.kind} proto must reference a grpc-proto target")

        out_dir = resolve_output_path(config_path, target.out_dir)
        source_root = resolve_output_path(config_path, target.source_root)
        overlay_name = target.overlay_name
        if target.kind == "wails-transport":
            overlay_name = overlay_name or default_wails_overlay_name(target.version or "v3")

        resolved.append(
            ResolvedApiTargetConfig(
                id=target.id,
                kind=target.kind,
                out_dir=out_dir,
                module=target.module,
                base_url=target.base_url,
                base_url_expr=target.base_url_expr,
                package=target.package,
                formats=tuple(target.formats),
                version=target.version,
                frontend_mode=target.frontend_mode,
                overlay_name=overlay_name,
                server=target.server,
                clients=tuple(target.clients),
                proto=target.proto,
                source_root=source_root,
                files=tuple(target.files),
                import_roots=resolve_unique_path_list(config_path, target.import_roots),
                go_package_prefix=target.go_package_prefix,
                python_package_root=target.python_package_root,
                include=normalize_selection_rules(target.include),
                exclude=normalize_selection_rules(target.exclude),
                proto_files=tuple(
                    ResolvedGrpcProtoFileConfig(
                        file=proto_file.file,
                        package=proto_file.package,
                        go_package=proto_file.go_package,
                        schema_modules=tuple(proto_file.schema_modules),
                        schema_names=tuple(proto_file.schema_names),
                        route_paths=tuple(proto_file.route_paths),
                        route_ids=tuple(proto_file.route_ids),
                        service_ids=tuple(proto_file.service_ids),
                        service=proto_file.service,
                    )
                    for proto_file in target.proto_files
                ),
            )
        )
    return tuple(resolved)
