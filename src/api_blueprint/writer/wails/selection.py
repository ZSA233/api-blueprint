from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from typing import Sequence

from api_blueprint.config import ResolvedWailsTargetConfig
from api_blueprint.engine.router import Router
from api_blueprint.route_selection import matches_selection_rule, normalize_selection_rules
from api_blueprint.writer.core.contracts import route_contract


@dataclass(frozen=True)
class WailsRouteSelection:
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "include", normalize_selection_rules(self.include))
        object.__setattr__(self, "exclude", normalize_selection_rules(self.exclude))

    def includes_route(self, router: Router) -> bool:
        route_name = route_contract(router).func_name
        if self.include and not any(self._matches(router, rule, route_name=route_name) for rule in self.include):
            return False
        if any(self._matches(router, rule, route_name=route_name) for rule in self.exclude):
            return False
        return True

    def _matches(self, router: Router, rule: str, *, route_name: str) -> bool:
        return matches_selection_rule(router, rule, route_name=route_name, label="[gen_wails]")


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
