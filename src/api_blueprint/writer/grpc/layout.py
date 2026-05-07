from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence


JsonObject = Mapping[str, Any]


class GrpcProtoFileRule(Protocol):
    file: str
    package: str | None
    go_package: str | None
    schema_modules: tuple[str, ...]
    schema_names: tuple[str, ...]
    route_paths: tuple[str, ...]
    route_ids: tuple[str, ...]
    service_ids: tuple[str, ...]
    service: str | None


@dataclass(frozen=True)
class ProtoFileLayout:
    file: str
    package: str | None = None
    go_package: str | None = None
    service: str | None = None


class GrpcProtoLayout:
    def __init__(self, rules: Sequence[GrpcProtoFileRule] = ()) -> None:
        self.rules = tuple(rules)

    def route_file(self, route: JsonObject) -> ProtoFileLayout | None:
        for rule in self.rules:
            if _matches_any(str(route.get("url") or ""), rule.route_paths):
                return _layout(rule)
            if _matches_any(str(route.get("id") or ""), rule.route_ids):
                return _layout(rule)
            if _matches_any(str(route.get("service_id") or ""), rule.service_ids):
                return _layout(rule)
        return None

    def schema_file(self, schema: JsonObject) -> ProtoFileLayout | None:
        for rule in self.rules:
            if _matches_any(str(schema.get("module") or ""), rule.schema_modules):
                return _layout(rule)
            schema_names = [
                str(schema.get("name") or ""),
                str(schema.get("identity") or ""),
                str(schema.get("qualname") or ""),
            ]
            if any(_matches_any(name, rule.schema_names) for name in schema_names):
                return _layout(rule)
        return None

    def enum_file(self, enum: JsonObject) -> ProtoFileLayout | None:
        for rule in self.rules:
            if _matches_any(str(enum.get("enum_module") or ""), rule.schema_modules):
                return _layout(rule)
            enum_names = [
                str(enum.get("enum") or ""),
                str(enum.get("enum_identity") or ""),
                str(enum.get("enum_qualname") or ""),
            ]
            if any(_matches_any(name, rule.schema_names) for name in enum_names):
                return _layout(rule)
        return None


def _layout(rule: GrpcProtoFileRule) -> ProtoFileLayout:
    return ProtoFileLayout(
        file=rule.file,
        package=rule.package,
        go_package=rule.go_package,
        service=rule.service,
    )


def _matches_any(value: str, patterns: Sequence[str]) -> bool:
    return any(fnmatch.fnmatchcase(value, pattern) for pattern in patterns)
