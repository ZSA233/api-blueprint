from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from api_blueprint.engine.connection import ConnectionKind
from api_blueprint.engine.router import Router
from api_blueprint.writer.core.planning import route_matches_rule


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
    if ":" in rule:
        scope, _pattern = rule.split(":", 1)
        if scope not in {"path", "tag", "group", "method", "name", "kind"}:
            raise ValueError(f"[kotlin-client] 不支持的 include/exclude 规则: {rule}")
    return route_matches_rule(_route_manifest(router, route_name=route_name), rule)


def _route_manifest(router: Router, *, route_name: str) -> dict[str, object]:
    root = router.group.root.strip("/") or "root"
    group = router.group.branch.strip("/") or root
    kind = "rpc" if router.connection_kind == ConnectionKind.RPC else router.connection_kind.value
    return {
        "id": f"{root}.{group}.{route_name}",
        "service_id": f"{root}.{group}",
        "kind": kind,
        "operation": route_name,
        "methods": list(router.methods),
        "url": router.url,
        "tags": list(router.tags),
    }


def normalize_rules(rules: Sequence[str]) -> tuple[str, ...]:
    return tuple(rule.strip() for rule in rules if rule.strip())
