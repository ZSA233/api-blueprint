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


@dataclass(frozen=True)
class ResolvedGrpcJobConfig:
    name: str
    preset: Literal["go", "python"]
    output: Path
    protos: tuple[str, ...]
    include_paths: tuple[Path, ...]


@dataclass(frozen=True)
class ResolvedGrpcConfig:
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


def resolve_config(path: str | Path | None) -> ResolvedConfig:
    normalized = normalize_config_path(path)
    raw = Config.load(normalized)

    goconf = raw.golang
    tsconf = raw.typescript
    grpcconf = raw.grpc
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
        ),
        grpc=None
        if grpcconf is None
        else ResolvedGrpcConfig(
            proto_root=resolve_output_path(normalized, grpcconf.proto_root)
            or normalized.parent.resolve(),
            include_paths=resolve_path_list(normalized, grpcconf.include_paths),
            jobs=tuple(
                ResolvedGrpcJobConfig(
                    name=job.name,
                    preset=job.preset,
                    output=resolve_output_path(normalized, job.output) or normalized.parent.resolve(),
                    protos=tuple(job.protos),
                    include_paths=resolve_path_list(normalized, job.include_paths),
                )
                for job in grpcconf.jobs
            ),
        ),
    )
