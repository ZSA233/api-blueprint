from __future__ import annotations

import fnmatch
from typing import Sequence

from api_blueprint.config import ResolvedWailsTargetConfig


def select_targets(
    targets: Sequence[ResolvedWailsTargetConfig],
    patterns: Sequence[str] = (),
) -> tuple[ResolvedWailsTargetConfig, ...]:
    if not patterns:
        return tuple(targets)

    unmatched = [
        pattern
        for pattern in patterns
        if not any(fnmatch.fnmatchcase(target.id, pattern) for target in targets)
    ]
    if unmatched:
        raise ValueError(f"[gen_wails] 未匹配到任何 target: {', '.join(unmatched)}")

    return tuple(
        target
        for target in targets
        if any(fnmatch.fnmatchcase(target.id, pattern) for pattern in patterns)
    )
