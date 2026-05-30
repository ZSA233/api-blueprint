from __future__ import annotations

from dataclasses import dataclass

from api_blueprint.engine.router import Router
from api_blueprint.route_selection import matches_selection_rule, normalize_selection_rules


@dataclass(frozen=True)
class SwiftRouteSelection:
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()

    def __init__(self, include=(), exclude=()):
        object.__setattr__(self, "include", normalize_selection_rules(include))
        object.__setattr__(self, "exclude", normalize_selection_rules(exclude))

    def includes(self, router: Router, *, route_name: str = "") -> bool:
        if self.include and not any(self._matches(router, rule, route_name=route_name) for rule in self.include):
            return False
        return not any(self._matches(router, rule, route_name=route_name) for rule in self.exclude)

    def _matches(self, router: Router, rule: str, *, route_name: str) -> bool:
        return matches_selection_rule(router, rule, route_name=route_name, label="[api-gen swift]")
