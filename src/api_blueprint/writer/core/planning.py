from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from typing import TYPE_CHECKING, Mapping, Sequence

from api_blueprint.config import ResolvedApiTargetConfig

if TYPE_CHECKING:
    from api_blueprint.contract import ContractGraph


RouteManifest = Mapping[str, object]


@dataclass(frozen=True)
class TargetCapability:
    implemented: bool
    routes: tuple[str, ...] = ()
    ignored_routes: tuple[str, ...] = ()
    requests: tuple[str, ...] = ()
    wrappers: tuple[str, ...] = ()
    reserved: bool = False
    transport: str | None = None
    outputs: tuple[str, ...] = ()
    inputs: tuple[str, ...] = ()
    frontend_modes: tuple[str, ...] = ()

    def to_manifest(self) -> dict[str, object]:
        manifest: dict[str, object] = {"implemented": self.implemented, "routes": list(self.routes)}
        if self.ignored_routes:
            manifest["ignored_routes"] = list(self.ignored_routes)
        if self.requests:
            manifest["requests"] = list(self.requests)
        if self.wrappers:
            manifest["wrappers"] = list(self.wrappers)
        if self.reserved:
            manifest["reserved"] = True
        if self.transport is not None:
            manifest["transport"] = self.transport
        if self.outputs:
            manifest["outputs"] = list(self.outputs)
        if self.inputs:
            manifest["inputs"] = list(self.inputs)
        if self.frontend_modes:
            manifest["frontend_modes"] = list(self.frontend_modes)
        return manifest


TARGET_CAPABILITIES: dict[str, TargetCapability] = {
    "contract": TargetCapability(implemented=True, outputs=("json", "markdown", "agent-json", "agent-markdown", "shards")),
    "go-server": TargetCapability(
        implemented=True,
        routes=("rpc", "legacy_ws", "stream", "channel"),
        requests=("query", "json", "form", "binary", "binary-schema", "open"),
        wrappers=("none", "general", "custom"),
    ),
    "go-client": TargetCapability(
        implemented=True,
        routes=("rpc", "legacy_ws", "stream", "channel"),
        requests=("query", "json", "form", "binary", "binary-schema", "open"),
        wrappers=("none", "general", "custom"),
        transport="injected",
    ),
    "typescript-client": TargetCapability(
        implemented=True,
        routes=("rpc", "legacy_ws", "stream", "channel"),
        requests=("query", "json", "form", "binary", "binary-schema", "open"),
        wrappers=("none", "general", "custom"),
        transport="injected",
    ),
    "kotlin-client": TargetCapability(
        implemented=True,
        routes=("rpc", "legacy_ws", "stream", "channel"),
        requests=("query", "json", "form", "binary", "binary-schema", "open"),
        wrappers=("none", "general", "custom"),
        transport="injected",
    ),
    "python-server": TargetCapability(
        implemented=True,
        routes=("rpc", "legacy_ws", "stream", "channel"),
        requests=("query", "json", "form", "binary", "open"),
        wrappers=("none", "general", "custom"),
    ),
    "python-client": TargetCapability(
        implemented=True,
        routes=("rpc", "legacy_ws", "stream", "channel"),
        requests=("query", "json", "form", "binary", "binary-schema", "open"),
        wrappers=("none", "general", "custom"),
        transport="injected",
    ),
    "http-transport": TargetCapability(implemented=True, routes=("rpc", "legacy_ws", "stream", "channel")),
    "wails-transport": TargetCapability(
        implemented=True,
        routes=("rpc", "legacy_ws", "stream", "channel"),
        frontend_modes=("external", "none"),
    ),
    "grpc-proto": TargetCapability(
        implemented=True,
        routes=("rpc", "stream", "channel"),
        ignored_routes=("legacy_ws",),
        outputs=("proto",),
    ),
    "grpc-go": TargetCapability(implemented=True, inputs=("proto",), outputs=("go", "grpc-go")),
    "grpc-python": TargetCapability(implemented=True, inputs=("proto",), outputs=("python", "grpc-python")),
}


def target_capability_manifest() -> dict[str, dict[str, object]]:
    return {kind: capability.to_manifest() for kind, capability in TARGET_CAPABILITIES.items()}


def capability_errors(
    graph: "ContractGraph",
    targets: Sequence[ResolvedApiTargetConfig],
) -> list[str]:
    routes = graph.to_manifest()["routes"]
    errors: list[str] = []
    for target in targets:
        capability = TARGET_CAPABILITIES.get(target.kind)
        if capability is None:
            errors.append(f"{target.kind} unsupported target capability: target[{target.id}]")
            continue
        if not capability.implemented:
            errors.append(f"{target.kind} is reserved but not implemented: target[{target.id}]")
            continue
        for route in routes:
            if not isinstance(route, Mapping):
                continue
            if not target_selects_route(target, route):
                continue
            errors.extend(_route_capability_errors(target, capability, route))
    return errors


def target_selects_route(target: ResolvedApiTargetConfig, route: RouteManifest) -> bool:
    if target.include and not any(route_matches_rule(route, rule) for rule in target.include):
        return False
    return not any(route_matches_rule(route, rule) for rule in target.exclude)


def route_matches_rule(route: RouteManifest, rule: str) -> bool:
    if ":" not in rule:
        key = "path"
        pattern = rule
    else:
        key, pattern = rule.split(":", 1)

    if key == "path":
        return fnmatch.fnmatchcase(_route_str(route, "url"), pattern)
    if key == "tag":
        tags = route.get("tags", [])
        return isinstance(tags, list) and any(fnmatch.fnmatchcase(str(tag), pattern) for tag in tags)
    if key == "group":
        return fnmatch.fnmatchcase(_route_str(route, "service_id").rsplit(".", 1)[-1], pattern.strip("/"))
    if key == "method":
        methods = route.get("methods", [])
        return isinstance(methods, list) and any(fnmatch.fnmatchcase(str(method), pattern.upper()) for method in methods)
    if key == "name":
        return fnmatch.fnmatchcase(_route_str(route, "operation"), pattern)
    if key == "kind":
        return fnmatch.fnmatchcase(_route_str(route, "kind"), pattern)
    return False


def _route_capability_errors(
    target: ResolvedApiTargetConfig,
    capability: TargetCapability,
    route: RouteManifest,
) -> list[str]:
    route_id = _route_str(route, "id")
    errors: list[str] = []
    route_kind = _route_str(route, "kind") or "rpc"
    if route_kind in capability.ignored_routes:
        return errors
    if capability.routes and route_kind not in capability.routes:
        errors.append(f"{target.kind} does not support {route_kind} route: {route_id}")

    request = route.get("request") or {}
    if capability.requests and isinstance(request, Mapping):
        for request_kind, manifest_key in (
            ("query", "query_model"),
            ("json", "json_model"),
            ("form", "form_model"),
            ("binary", "binary_model"),
            ("binary-schema", "binary_schema"),
            ("open", "open_model"),
        ):
            if request.get(manifest_key) is not None and request_kind not in capability.requests:
                errors.append(f"{target.kind} does not support {request_kind} request route: {route_id}")

    response = route.get("response") or {}
    if capability.wrappers and isinstance(response, Mapping):
        wrapper = _wrapper_kind(response.get("wrapper"))
        if wrapper not in capability.wrappers:
            errors.append(f"{target.kind} does not support {wrapper} response wrapper route: {route_id}")
    return errors


def _wrapper_kind(wrapper: object) -> str:
    if wrapper in {None, "NoneWrapper"}:
        return "none"
    if wrapper == "GeneralWrapper":
        return "general"
    return "custom"


def _route_str(route: RouteManifest, key: str) -> str:
    value = route.get(key)
    return "" if value is None else str(value)
