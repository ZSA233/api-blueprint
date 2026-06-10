from __future__ import annotations

import fnmatch
from typing import Sequence

from api_blueprint.engine.router import Router


ALLOWED_ROUTE_SELECTION_SCOPES = frozenset({"path", "tag", "group", "method", "name", "kind"})


def normalize_selection_rules(rules: Sequence[str]) -> tuple[str, ...]:
    return tuple(rule.strip() for rule in rules if rule.strip())


def validate_selection_rules(rules: Sequence[str], *, label: str) -> tuple[str, ...]:
    normalized = normalize_selection_rules(rules)
    for rule in normalized:
        parse_selection_rule(rule, label=label)
    return normalized


def parse_selection_rule(rule: str, *, label: str) -> tuple[str, str]:
    normalized = rule.strip()
    if not normalized:
        raise ValueError(f"{label} 不支持的 include/exclude 规则: {rule}")

    if ":" not in normalized:
        return "path", normalized

    scope, pattern = normalized.split(":", 1)
    if scope not in ALLOWED_ROUTE_SELECTION_SCOPES or not pattern:
        raise ValueError(f"{label} 不支持的 include/exclude 规则: {rule}")
    return scope, pattern


def matches_selection_rule(
    router: Router,
    rule: str,
    *,
    route_name: str,
    label: str,
) -> bool:
    scope, pattern = parse_selection_rule(rule, label=label)

    if scope == "path":
        return fnmatch.fnmatchcase(router.url, pattern)
    if scope == "tag":
        return any(fnmatch.fnmatchcase(tag, pattern) for tag in router.tags)
    if scope == "group":
        return fnmatch.fnmatchcase(router.group.branch.strip("/"), pattern.strip("/"))
    if scope == "method":
        methods = tuple(method.upper() for method in router.methods)
        return any(fnmatch.fnmatchcase(method, pattern.upper()) for method in methods)
    if scope == "name":
        return fnmatch.fnmatchcase(route_name, pattern)
    if scope == "kind":
        return fnmatch.fnmatchcase(getattr(router, "kind", "rpc"), pattern)
    raise ValueError(f"{label} 不支持的 include/exclude 规则: {rule}")
