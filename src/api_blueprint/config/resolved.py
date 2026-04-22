from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from api_blueprint.config.loader import normalize_config_path
from api_blueprint.config.models import Config


@dataclass(frozen=True)
class ResolvedTargetConfig:
    output: Path | None
    upstream: str | None = None
    module: str | None = None
    base_url: str | None = None
    base_url_expr: str | None = None


@dataclass(frozen=True)
class ResolvedGrpcJobConfig:
    name: str
    preset: Literal["go", "python"]
    output: Path
    proto_root: Path
    protos: tuple[str, ...]
    include_paths: tuple[Path, ...]
    layout: Literal["source_relative", "go_package"]
    module: str | None = None


@dataclass(frozen=True)
class ResolvedGrpcTargetConfig:
    id: str
    lang: Literal["go", "python"]
    out_dir: Path
    source_root: Path
    files: tuple[str, ...]
    import_roots: tuple[Path, ...]


@dataclass(frozen=True)
class ResolvedGrpcConfig:
    source_root: Path
    import_roots: tuple[Path, ...]
    targets: tuple[ResolvedGrpcTargetConfig, ...]
    proto_root: Path
    include_paths: tuple[Path, ...]
    jobs: tuple[ResolvedGrpcJobConfig, ...]


@dataclass(frozen=True)
class ResolvedConfig:
    path: Path
    project_root: Path
    entrypoint_root: Path
    raw: Config
    golang: ResolvedTargetConfig | None
    typescript: ResolvedTargetConfig | None
    grpc: ResolvedGrpcConfig | None


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


def choose_path_entries(
    primary: list[str] | tuple[str, ...],
    fallback: list[str] | tuple[str, ...],
) -> list[str] | tuple[str, ...]:
    return primary if primary else fallback


def resolve_config(path: str | Path | None) -> ResolvedConfig:
    normalized = normalize_config_path(path)
    raw = Config.load(normalized)

    goconf = raw.golang
    tsconf = raw.typescript
    grpcconf = raw.grpc
    target_import_entries = (
        choose_path_entries(grpcconf.import_roots, grpcconf.include_paths)
        if grpcconf is not None
        else ()
    )
    job_include_entries = (
        choose_path_entries(grpcconf.include_paths, grpcconf.import_roots)
        if grpcconf is not None
        else ()
    )
    resolved_target_source_root = (
        resolve_output_path(normalized, grpcconf.source_root or grpcconf.proto_root)
        if grpcconf is not None
        else None
    )
    resolved_target_import_roots = (
        resolve_unique_path_list(normalized, target_import_entries)
        if grpcconf is not None
        else ()
    )
    resolved_job_proto_root = (
        resolve_output_path(normalized, grpcconf.proto_root or grpcconf.source_root)
        if grpcconf is not None
        else None
    )
    resolved_job_include_paths = (
        resolve_unique_path_list(normalized, job_include_entries)
        if grpcconf is not None
        else ()
    )
    return ResolvedConfig(
        path=normalized,
        project_root=normalized.parent,
        entrypoint_root=normalized.parent,
        raw=raw,
        golang=None
        if goconf is None
        else ResolvedTargetConfig(
            output=resolve_output_path(normalized, goconf.codegen_output),
            upstream=goconf.upstream,
            module=goconf.module,
        ),
        typescript=None
        if tsconf is None
        else ResolvedTargetConfig(
            output=resolve_output_path(normalized, tsconf.codegen_output or "typescript"),
            upstream=tsconf.upstream,
            base_url=tsconf.base_url,
            base_url_expr=tsconf.base_url_expr,
        ),
        grpc=None
        if grpcconf is None
        else ResolvedGrpcConfig(
            source_root=resolved_target_source_root or normalized.parent.resolve(),
            import_roots=resolved_target_import_roots,
            targets=tuple(
                ResolvedGrpcTargetConfig(
                    id=target.id,
                    lang=target.lang,
                    out_dir=resolve_output_path(normalized, target.out_dir) or normalized.parent.resolve(),
                    source_root=resolve_output_path(normalized, target.source_root)
                    or resolved_target_source_root
                    or normalized.parent.resolve(),
                    files=tuple(target.files),
                    import_roots=resolve_path_list(normalized, target.import_roots),
                )
                for target in grpcconf.targets
            ),
            proto_root=resolved_job_proto_root or normalized.parent.resolve(),
            include_paths=resolved_job_include_paths,
            jobs=tuple(
                ResolvedGrpcJobConfig(
                    name=job.name,
                    preset=job.preset,
                    output=resolve_output_path(normalized, job.output) or normalized.parent.resolve(),
                    proto_root=resolve_output_path(normalized, job.proto_root)
                    or resolved_job_proto_root
                    or normalized.parent.resolve(),
                    protos=tuple(job.protos),
                    include_paths=resolve_path_list(normalized, job.include_paths),
                    layout=job.layout,
                    module=job.module,
                )
                for job in grpcconf.jobs
            ),
        ),
    )
