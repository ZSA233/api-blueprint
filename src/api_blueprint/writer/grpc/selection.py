from __future__ import annotations

import fnmatch
from typing import Callable, Sequence, TypeVar

from api_blueprint.config import ResolvedGrpcJobConfig, ResolvedGrpcTargetConfig


NamedItem = TypeVar("NamedItem", ResolvedGrpcJobConfig, ResolvedGrpcTargetConfig)


def select_jobs(
    jobs: Sequence[ResolvedGrpcJobConfig],
    patterns: Sequence[str] = (),
) -> tuple[ResolvedGrpcJobConfig, ...]:
    return _select_named_items(
        jobs,
        patterns,
        get_name=lambda job: job.name,
        label="legacy/raw job",
    )


def select_targets(
    targets: Sequence[ResolvedGrpcTargetConfig],
    patterns: Sequence[str] = (),
) -> tuple[ResolvedGrpcTargetConfig, ...]:
    return _select_named_items(
        targets,
        patterns,
        get_name=lambda target: target.id,
        label="target",
    )


def _select_named_items(
    items: Sequence[NamedItem],
    patterns: Sequence[str],
    *,
    get_name: Callable[[NamedItem], str],
    label: str,
) -> tuple[NamedItem, ...]:
    if not patterns:
        return tuple(items)

    unmatched = [
        pattern
        for pattern in patterns
        if not any(fnmatch.fnmatchcase(get_name(item), pattern) for item in items)
    ]
    if unmatched:
        raise ValueError(f"[gen_grpc] 未匹配到任何{label}: {', '.join(unmatched)}")

    return tuple(item for item in items if any(fnmatch.fnmatchcase(get_name(item), pattern) for pattern in patterns))
