from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from api_blueprint.writer.core.planning import route_matches_rule


@dataclass(frozen=True)
class JavaRouteSelection:
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()

    def includes(self, route: Mapping[str, object]) -> bool:
        if self.include and not any(matches_rule(route, rule) for rule in self.include):
            return False
        if any(matches_rule(route, rule) for rule in self.exclude):
            return False
        return True


def matches_rule(route: Mapping[str, object], rule: str) -> bool:
    if ":" in rule:
        scope, _pattern = rule.split(":", 1)
        if scope not in {"path", "tag", "group", "method", "name", "kind"}:
            raise ValueError(f"[java] 不支持的 include/exclude 规则: {rule}")
    return route_matches_rule(route, rule)


def normalize_rules(rules: Sequence[str]) -> tuple[str, ...]:
    return tuple(rule.strip() for rule in rules if rule.strip())
