from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from typing import Sequence

from api_blueprint.engine.router import Router


@dataclass(frozen=True)
class KotlinRouteSelection:
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()

    def includes(self, router: Router, *, route_name: str) -> bool:
        if self.include and not any(matches_rule(router, rule, route_name=route_name) for rule in self.include):
            return False
        if any(matches_rule(router, rule, route_name=route_name) for rule in self.exclude):
            return False
        return True


def matches_rule(router: Router, rule: str, *, route_name: str) -> bool:
    scope, _, pattern = rule.partition(":")
    if not pattern:
        scope = "path"
        pattern = rule

    if scope == "path":
        return fnmatch.fnmatchcase(router.url, pattern)
    if scope == "tag":
        return any(fnmatch.fnmatchcase(tag, pattern) for tag in router.tags)
    if scope == "group":
        return fnmatch.fnmatchcase(router.group.branch.strip("/"), pattern.strip("/"))
    if scope == "method":
        return any(fnmatch.fnmatchcase(method, pattern.upper()) for method in router.methods)
    if scope == "name":
        return fnmatch.fnmatchcase(route_name, pattern)
    raise ValueError(f"[gen_kotlin] 不支持的 include/exclude 规则: {rule}")


def normalize_rules(rules: Sequence[str]) -> tuple[str, ...]:
    return tuple(rule.strip() for rule in rules if rule.strip())

