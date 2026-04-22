from __future__ import annotations

import fnmatch
import glob
from pathlib import Path
from typing import Sequence

from api_blueprint.config import ResolvedGrpcJobConfig

from .models import GrpcGenerationJob


def select_jobs(
    jobs: Sequence[ResolvedGrpcJobConfig],
    patterns: Sequence[str] = (),
) -> tuple[ResolvedGrpcJobConfig, ...]:
    if not patterns:
        return tuple(jobs)

    unmatched = [pattern for pattern in patterns if not any(fnmatch.fnmatchcase(job.name, pattern) for job in jobs)]
    if unmatched:
        raise ValueError(f"[gen_grpc] 未匹配到任何job: {', '.join(unmatched)}")

    return tuple(job for job in jobs if any(fnmatch.fnmatchcase(job.name, pattern) for pattern in patterns))


def expand_job(
    job: ResolvedGrpcJobConfig,
    *,
    proto_root: Path,
    global_include_paths: Sequence[Path] = (),
) -> GrpcGenerationJob:
    proto_root = proto_root.resolve()
    include_paths = _merge_include_paths(global_include_paths, job.include_paths)
    proto_files = _expand_patterns(proto_root, job.name, job.protos)
    return GrpcGenerationJob(
        name=job.name,
        preset=job.preset,
        output=job.output.resolve(),
        proto_root=proto_root,
        include_paths=include_paths,
        proto_patterns=job.protos,
        proto_files=proto_files,
    )


def _merge_include_paths(*groups: Sequence[Path]) -> tuple[Path, ...]:
    merged: list[Path] = []
    seen: set[str] = set()
    for group in groups:
        for path in group:
            resolved = path.resolve()
            key = str(resolved)
            if key in seen:
                continue
            seen.add(key)
            merged.append(resolved)
    return tuple(merged)


def _expand_patterns(proto_root: Path, job_name: str, patterns: Sequence[str]) -> tuple[Path, ...]:
    expanded: list[Path] = []
    seen: set[str] = set()
    for pattern in patterns:
        matches = _expand_single_pattern(proto_root, pattern)
        if not matches:
            raise ValueError(f"[gen_grpc] job[{job_name}] proto pattern 未匹配到文件: {pattern}")
        for match in matches:
            key = match.as_posix()
            if key in seen:
                continue
            seen.add(key)
            expanded.append(match)
    return tuple(expanded)


def _expand_single_pattern(proto_root: Path, pattern: str) -> tuple[Path, ...]:
    if glob.has_magic(pattern):
        matches = sorted(path for path in proto_root.glob(pattern) if path.is_file())
    else:
        candidate = (proto_root / pattern).resolve()
        if not candidate.is_file():
            return ()
        matches = [candidate]

    return tuple(_relative_to_root(proto_root, match) for match in matches)


def _relative_to_root(proto_root: Path, path: Path) -> Path:
    resolved_root = proto_root.resolve()
    resolved_path = path.resolve()
    try:
        return resolved_path.relative_to(resolved_root)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"[gen_grpc] proto 文件超出proto_root范围: {resolved_path}") from exc
